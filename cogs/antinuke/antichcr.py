import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz
from discord.ui import Select, View, Modal, TextInput

class AntiChannelCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.event_limits = {}
        self.cooldowns = {}
        self.bot.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        """Initialize the database and create tables if they don't exist."""
        self.db = await aiosqlite.connect('db/anti.db')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS antinuke (
                guild_id INTEGER PRIMARY KEY,
                status BOOLEAN
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS limit_settings (
                guild_id INTEGER,
                action_type TEXT,
                action_limit INTEGER,
                time_window INTEGER,
                PRIMARY KEY (guild_id, action_type)
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS antinuke_logging (
                guild_id INTEGER PRIMARY KEY,
                log_channel INTEGER
            )
        ''')
        await self.db.commit()

    def can_fetch_audit(self, guild_id, event_name, max_requests=6, interval=10, cooldown_duration=300):
        """Check if audit logs can be fetched based on rate limits."""
        now = datetime.datetime.now()
        self.event_limits.setdefault(guild_id, {}).setdefault(event_name, []).append(now)

        timestamps = self.event_limits[guild_id][event_name]
        timestamps = [t for t in timestamps if (now - t).total_seconds() <= interval]
        self.event_limits[guild_id][event_name] = timestamps

        if len(timestamps) > max_requests:
            self.cooldowns.setdefault(guild_id, {})[event_name] = now
            return False
        return True

    async def fetch_audit_logs(self, guild, action, target_id, delay=1):
        """Fetch audit logs for a specific action and target."""
        if not guild.me.guild_permissions.view_audit_log:
            return None
        try:
            async for entry in guild.audit_logs(action=action, limit=1):
                if entry.target.id == target_id:
                    now = datetime.datetime.now(pytz.utc)
                    if (now - entry.created_at).total_seconds() * 1000 >= 3600000:
                        return None
                    await asyncio.sleep(delay)
                    return entry
        except Exception:
            pass
        return None

    async def move_role_below_bot(self, guild):
        """Move the most populated role below the bot's top role."""
        bot_top_role = guild.me.top_role
        most_populated_role = max(
            [role for role in guild.roles if role.position < bot_top_role.position and not role.managed and role != guild.default_role],
            key=lambda r: len(r.members),
            default=None
        )
        if most_populated_role:
            try:
                await most_populated_role.edit(position=bot_top_role.position - 1, reason="Emergency: Adjusting roles for security")
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def delete_channel_and_ban(self, channel, executor, delay=2, retries=3):
        """Delete a channel and ban the executor."""
        while retries > 0:
            try:
                await channel.delete(reason="Channel created by unwhitelisted user")
                await channel.guild.ban(executor, reason="Channel Create | Unwhitelisted User")
                return
            except discord.Forbidden:
                return
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = e.response.headers.get('Retry-After', delay)
                    await asyncio.sleep(float(retry_after))
                    retries -= 1
            except Exception:
                return

    async def get_log_channel(self, guild_id):
        """Get the logging channel ID for a guild."""
        async with self.db.execute('SELECT log_channel FROM antinuke_logging WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def log_action(self, guild_id, action, user, reason=None):
        """Log an action to the logging channel stored in the database."""
        log_channel_id = await self.get_log_channel(guild_id)
        if not log_channel_id:
            return  # No log channel configured
        
        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            return  # Channel not found or inaccessible
        guild_name = self.bot.get_guild(guild_id).name
        embed = discord.Embed(
            title=f"Action: {action.replace('_', ' ').title()}",
            description=f"**User:** {user.mention} (`{user.id}`)\n**Reason:** {reason or 'No reason provided'}",
            color=discord.Color.red()
        )
        embed.add_field(name="Server", value=guild_name, inline=False)
        embed.add_field(name="Action Time", value=datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'), inline=False)
        embed.set_footer(text=f"Action performed at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Handle channel creation events."""
        guild = channel.guild

        async with self.db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)) as cursor:
            antinuke_status = await cursor.fetchone()
        if not antinuke_status or not antinuke_status[0]:
            return

        if not self.can_fetch_audit(guild.id, "channel_create"):
            await self.move_role_below_bot(guild)
            await asyncio.sleep(5)

        logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.channel_create, channel.id, delay=2)
        if logs is None:
            return

        executor = logs.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return

        async with self.db.execute("SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?", (guild.id, executor.id)) as cursor:
            if await cursor.fetchone():
                return

        async with self.db.execute("SELECT chcr FROM whitelisted_users WHERE guild_id = ? AND user_id = ?", (guild.id, executor.id)) as cursor:
            whitelist_status = await cursor.fetchone()
        if whitelist_status and whitelist_status[0]:
            return

        await self.delete_channel_and_ban(channel, executor, delay=2)
        await self.log_action(guild.id, 'Anti-nuke Alert', executor, reason="Channel created by unwhitelisted user")

async def setup(bot):
    await bot.add_cog(AntiChannelCreate(bot))
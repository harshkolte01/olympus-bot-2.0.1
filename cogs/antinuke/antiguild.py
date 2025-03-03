import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import time  # Added for time measurement

class AntiGuildUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.event_limits = {}
        self.cooldowns = {}
        self.db = None  # Initialize db attribute
        self.bot.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        """Initialize the SQLite database connection."""
        try:
            self.db = await aiosqlite.connect('db/anti.db')
            await self.db.execute('''CREATE TABLE IF NOT EXISTS antinuke (
                guild_id INTEGER PRIMARY KEY,
                status INTEGER DEFAULT 0
            )''')
            await self.db.execute('''CREATE TABLE IF NOT EXISTS extraowners (
                guild_id INTEGER,
                owner_id INTEGER,
                PRIMARY KEY (guild_id, owner_id)
            )''')
            await self.db.execute('''CREATE TABLE IF NOT EXISTS whitelisted_users (
                guild_id INTEGER,
                user_id INTEGER,
                serverup INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )''')
            await self.db.execute('''CREATE TABLE IF NOT EXISTS antinuke_logging (
                guild_id INTEGER PRIMARY KEY,
                log_channel INTEGER
            )''')
            await self.db.commit()
            print("AntiGuildUpdate database initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize AntiGuildUpdate database: {e}")

    async def fetch_audit_logs(self, guild, action):
        """Fetch the latest audit log entry for a specific action."""
        if not guild.me.guild_permissions.view_audit_log:
            print(f"Missing view_audit_log permission in guild {guild.id}")
            return None
        try:
            async for entry in guild.audit_logs(action=action, limit=1):
                now = discord.utils.utcnow()
                if (now - entry.created_at).total_seconds() > 3600:  # Older than 1 hour
                    return None
                return entry
        except discord.Forbidden:
            print(f"Forbidden access to audit logs in guild {guild.id}")
        except Exception as e:
            print(f"Error fetching audit logs in guild {guild.id}: {e}")
        return None

    def can_fetch_audit(self, guild_id, event_name, max_requests=5, interval=10, cooldown_duration=300):
        """Rate limit audit log fetching."""
        now = datetime.datetime.now()
        self.event_limits.setdefault(guild_id, {}).setdefault(event_name, []).append(now)

        timestamps = self.event_limits[guild_id][event_name]
        timestamps = [t for t in timestamps if (now - t).total_seconds() <= interval]
        self.event_limits[guild_id][event_name] = timestamps

        if guild_id in self.cooldowns and event_name in self.cooldowns[guild_id]:
            if (now - self.cooldowns[guild_id][event_name]).total_seconds() < cooldown_duration:
                return False
            del self.cooldowns[guild_id][event_name]

        if len(timestamps) > max_requests:
            self.cooldowns.setdefault(guild_id, {})[event_name] = now
            return False
        return True

    async def get_log_channel(self, guild_id):
        """Get the logging channel ID for a guild."""
        if not self.db:
            print("Database not initialized for logging.")
            return None
        async with self.db.execute('SELECT log_channel FROM antinuke_logging WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def log_action(self, guild_id, action, user, reason=None, action_time=None):
        """Log an action to the logging channel with action time."""
        log_channel_id = await self.get_log_channel(guild_id)
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            print(f"Log channel {log_channel_id} not found or inaccessible.")
            return

        guild = self.bot.get_guild(guild_id)
        guild_name = guild.name if guild else "Unknown Guild"

        embed = discord.Embed(
            title=f"Action: {action.replace('_', ' ').title()}",
            description=f"**User:** {user.mention} (`{user.id}`)\n**Reason:** {reason or 'No reason provided'}",
            color=discord.Color.red()
        )
        embed.add_field(name="Server", value=guild_name, inline=False)
        embed.add_field(name="Action Time", value=discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'), inline=False)
        if action_time is not None:
            embed.add_field(name="Action Duration", value=f"{action_time:.2f} seconds", inline=False)
        embed.set_footer(text=f"Logged at {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Cannot send log to {log_channel_id}: Missing permissions.")
        except discord.HTTPException as e:
            print(f"Failed to send log to {log_channel_id}: {e}")

    async def is_blacklisted_guild(self, guild_id):
        """Check if a guild is blacklisted."""
        async with aiosqlite.connect('db/block.db') as block_db:
            async with block_db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (str(guild_id),)) as cursor:
                return await cursor.fetchone() is not None

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        guild = before
        if await self.is_blacklisted_guild(guild.id):
            return

        if not self.db:
            print("Database not initialized yet.")
            return

        async with self.db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)) as cursor:
            antinuke_status = await cursor.fetchone()
        if not antinuke_status or not antinuke_status[0]:
            return

        if not self.can_fetch_audit(guild.id, 'guild_update'):
            return

        logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.guild_update)
        if logs is None:
            return

        executor = logs.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return

        async with self.db.execute("SELECT serverup FROM whitelisted_users WHERE guild_id = ? AND user_id = ?", 
                                   (guild.id, executor.id)) as cursor:
            whitelist_status = await cursor.fetchone()
        if whitelist_status and whitelist_status[0]:
            return

        async with self.db.execute("SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?", 
                                   (guild.id, executor.id)) as cursor:
            extra_owner_status = await cursor.fetchone()
        if extra_owner_status:
            return

        # Measure the time taken for the action
        start_time = time.perf_counter()
        await self.ban_executor_and_revert_changes(before, after, executor)
        end_time = time.perf_counter()
        action_time = end_time - start_time

        # Log the action with the time taken
        await self.log_action(guild.id, "guild_update", executor, "Unwhitelisted user updated the guild", action_time)

    async def ban_executor_and_revert_changes(self, before, after, executor):
        """Ban the executor and revert guild changes."""
        retries = 3
        while retries > 0:
            try:
                await self.ban_executor(before, executor)
                await self.revert_guild_changes(before, after)
                print(f"Banned {executor.id} and reverted guild changes in guild {before.id}")
                return
            except discord.Forbidden:
                print(f"Missing permissions in guild {before.id}")
                return
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limit
                    retry_after = float(e.response.headers.get('Retry-After', 1))
                    print(f"Rate limited in guild {before.id}. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                    retries -= 1
                else:
                    print(f"HTTP error in guild {before.id}: {e}")
                    return
            except Exception as e:
                print(f"Unexpected error in guild {before.id}: {e}")
                return
        print(f"Failed to ban executor or revert changes in guild {before.id} after retries")

    async def ban_executor(self, guild, executor):
        """Ban the executor."""
        retries = 3
        reason = "Guild Update | Unwhitelisted User"
        while retries > 0:
            try:
                await guild.ban(executor, reason=reason)
                print(f"Banned {executor.id} in guild {guild.id}")
                return
            except discord.Forbidden:
                print(f"Missing permissions to ban {executor.id} in guild {guild.id}")
                return
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limit
                    retry_after = float(e.response.headers.get('Retry-After', 1))
                    print(f"Rate limited banning {executor.id} in guild {guild.id}. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                    retries -= 1
                else:
                    print(f"HTTP error banning {executor.id} in guild {guild.id}: {e}")
                    return
            except Exception as e:
                print(f"Unexpected error banning {executor.id} in guild {guild.id}: {e}")
                return
        print(f"Failed to ban {executor.id} in guild {guild.id} after retries")

    async def revert_guild_changes(self, before, after):
        """Revert guild changes to the previous state."""
        retries = 3
        reason = "Guild Update | Unwhitelisted User"
        while retries > 0:
            try:
                kwargs = {}
                if before.name != after.name:
                    kwargs["name"] = before.name
                if before.icon != after.icon:
                    kwargs["icon"] = before.icon
                if before.splash != after.splash:
                    kwargs["splash"] = before.splash
                if before.banner != after.banner:
                    kwargs["banner"] = before.banner
                if kwargs:  # Only edit if there are changes
                    await after.edit(**kwargs, reason=reason)
                    print(f"Reverted guild changes in guild {after.id}")
                return
            except discord.Forbidden:
                print(f"Missing permissions to revert guild changes in guild {after.id}")
                return
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limit
                    retry_after = float(e.response.headers.get('Retry-After', 1))
                    print(f"Rate limited reverting guild {after.id}. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                    retries -= 1
                else:
                    print(f"HTTP error reverting guild {after.id}: {e}")
                    return
            except Exception as e:
                print(f"Unexpected error reverting guild {after.id}: {e}")
                return
        print(f"Failed to revert guild changes in guild {after.id} after retries")

    def cog_unload(self):
        """Clean up when the cog is unloaded."""
        if self.db:
            asyncio.create_task(self.db.close())

async def setup(bot):
    await bot.add_cog(AntiGuildUpdate(bot))
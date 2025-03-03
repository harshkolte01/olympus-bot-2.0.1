import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
from datetime import timedelta

class AntiEveryone(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.event_limits = {}
        self.db = None  # Initialize db attribute
        self.bot.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        """Initialize the SQLite database connection."""
        try:
            self.db = await aiosqlite.connect('db/anti.db')
            # Create tables if they don’t exist
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
                meneve INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )''')
            await self.db.execute('''CREATE TABLE IF NOT EXISTS antinuke_logging (
                guild_id INTEGER PRIMARY KEY,
                log_channel INTEGER
            )''')
            await self.db.commit()
            print("Database initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize database: {e}")

    async def can_message_delete(self, guild_id, event_name, max_requests=5, interval=10, cooldown_duration=300):
        now = datetime.datetime.now()
        self.event_limits.setdefault(guild_id, {}).setdefault(event_name, []).append(now)

        timestamps = self.event_limits[guild_id][event_name]
        timestamps = [t for t in timestamps if (now - t).total_seconds() <= interval]
        self.event_limits[guild_id][event_name] = timestamps

        return len(timestamps) <= max_requests

    async def get_log_channel(self, guild_id):
        """Get the logging channel ID for a guild."""
        if not self.db:
            return None
        async with self.db.execute('SELECT log_channel FROM antinuke_logging WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def log_action(self, guild_id, action, user, reason=None):
        """Log an action to the logging channel stored in the database."""
        log_channel_id = await self.get_log_channel(guild_id)
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            return

        guild = self.bot.get_guild(guild_id)
        guild_name = guild.name if guild else "Unknown Guild"

        embed = discord.Embed(
            title=f"Action: {action.replace('_', ' ').title()}",
            description=f"**User:** {user.mention} (`{user.id}`)\n**Reason:** {reason or 'No reason provided'}",
            color=discord.Color.red()
        )
        embed.add_field(name="Server", value=guild_name, inline=False)
        embed.add_field(name="Action Time", value=datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'), inline=False)
        embed.set_footer(text=f"Action performed at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Cannot send log message to channel {log_channel_id}: Missing permissions.")
        except discord.HTTPException as e:
            print(f"Failed to send log message: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or not message.mention_everyone:
            return

        guild = message.guild

        if not self.db:
            print("Database not initialized yet.")
            return

        async with self.db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)) as cursor:
            antinuke_status = await cursor.fetchone()

        if not antinuke_status or not antinuke_status[0]:
            return

        if message.author.id in {guild.owner_id, self.bot.user.id}:
            return

        async with self.db.execute("SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?", (guild.id, message.author.id)) as cursor:
            extraowner_status = await cursor.fetchone()

        if extraowner_status:
            return

        async with self.db.execute("SELECT meneve FROM whitelisted_users WHERE guild_id = ? AND user_id = ?", (guild.id, message.author.id)) as cursor:
            whitelist_status = await cursor.fetchone()

        if whitelist_status and whitelist_status[0]:
            return

        if not await self.can_message_delete(guild.id, 'mention_everyone'):
            return

        try:
            await self.timeout_user(message.author)
            await self.log_action(guild.id, "mention_everyone", message.author)
            await self.delete_everyone_messages(message.channel)
        except Exception as e:
            print(f"Error handling @everyone mention from {message.author.id}: {e}")

    async def timeout_user(self, user, duration=3600):  # Default 1 hour
        retries = 3
        while retries > 0:
            try:
                await user.edit(timed_out_until=discord.utils.utcnow() + timedelta(seconds=duration), reason="Mentioned Everyone/Here | Unwhitelisted User")
                print(f"Timed out {user.id} successfully.")
                return
            except discord.Forbidden:
                print(f"Cannot timeout {user.id}: Missing permissions.")
                return
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limit
                    retry_after = float(e.response.headers.get('Retry-After', 1))
                    print(f"Rate limited while timing out {user.id}. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                    retries -= 1
                else:
                    print(f"HTTP error timing out {user.id}: {e}")
                    return
            except Exception as e:
                print(f"Unexpected error timing out {user.id}: {e}")
                return
        print(f"Failed to timeout {user.id} after {retries} attempts.")

    async def delete_everyone_messages(self, channel):
        retries = 3
        while retries > 0:
            try:
                deleted = 0
                async for msg in channel.history(limit=100):
                    if msg.mention_everyone:
                        await msg.delete()
                        deleted += 1
                        await asyncio.sleep(0.5)  # Small delay to avoid rate limits
                print(f"Deleted {deleted} @everyone messages.")
                return
            except discord.Forbidden:
                print(f"Cannot delete messages in {channel.id}: Missing permissions.")
                return
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limit
                    retry_after = float(e.response.headers.get('Retry-After', 1))
                    print(f"Rate limited while deleting messages. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                    retries -= 1
                else:
                    print(f"HTTP error deleting messages: {e}")
                    return
            except Exception as e:
                print(f"Unexpected error deleting messages: {e}")
                return
        print(f"Failed to delete messages after {retries} attempts.")

    def cog_unload(self):
        """Clean up when the cog is unloaded."""
        if self.db:
            asyncio.create_task(self.db.close())

async def setup(bot):
    await bot.add_cog(AntiEveryone(bot))
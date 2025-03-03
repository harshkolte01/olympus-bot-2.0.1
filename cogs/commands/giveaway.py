import discord
from discord.ext import commands, tasks
import aiosqlite
import asyncio
import datetime
import random
import logging
import os
import aiohttp

# Setup logging
logging.basicConfig(level=logging.INFO)

# Database setup
db_folder = 'db'
db_file = 'giveaways.db'
db_path = os.path.join(db_folder, db_file)

# Time conversion utility
def convert(time_str):
    """Convert time string to seconds."""
    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    unit = time_str[-1]
    if unit not in time_dict:
        return -1
    try:
        val = int(time_str[:-1])
        if val <= 0:
            return -2
        return val * time_dict[unit]
    except ValueError:
        return -3

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        self.GiveawayEnd = tasks.loop(seconds=5)(self.check_for_ended_giveaways)

    ### Lifecycle Management
    async def cog_load(self):
        """Initialize database connection and start giveaway end checker."""
        if not os.path.exists(db_folder):
            os.makedirs(db_folder)
        self.connection = await aiosqlite.connect(self.db_path)
        self.cursor = await self.connection.cursor()
        await self.create_table()
        await self.check_for_ended_giveaways()
        self.GiveawayEnd.start()

    async def cog_unload(self):
        """Clean up resources on cog unload."""
        if self.connection:
            await self.connection.close()
        self.GiveawayEnd.stop()

    async def create_table(self):
        """Create the Giveaway table if it doesn't exist."""
        await self.cursor.execute('''CREATE TABLE IF NOT EXISTS Giveaway (
            guild_id INTEGER,
            host_id INTEGER,
            start_time TIMESTAMP,
            ends_at TIMESTAMP,
            prize TEXT,
            winners INTEGER,
            message_id INTEGER,
            channel_id INTEGER,
            PRIMARY KEY (guild_id, message_id)
        )''')
        await self.connection.commit()

    ### Giveaway Management
    async def check_for_ended_giveaways(self):
        """Check for and end giveaways that have reached their end time."""
        current_time = datetime.datetime.now().timestamp()
        await self.cursor.execute("SELECT ends_at, guild_id, message_id, host_id, winners, prize, channel_id FROM Giveaway WHERE ends_at <= ?", (current_time,))
        ended_giveaways = await self.cursor.fetchall()
        for giveaway in ended_giveaways:
            await self.end_giveaway(giveaway)

    async def end_giveaway(self, giveaway):
        """End a giveaway and announce winners."""
        ends_at, guild_id, message_id, host_id, winners, prize, channel_id = giveaway
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                await self.delete_giveaway(guild_id, message_id)
                return

            channel = guild.get_channel(channel_id)
            if not channel:
                await self.delete_giveaway(guild_id, message_id)
                return

            try:
                message = await channel.fetch_message(message_id)
                users = [user.id async for user in message.reactions[0].users() if user.id != self.bot.user.id]
                if not users:
                    await message.reply(f"No one won the **{prize}** giveaway due to insufficient participants.")
                else:
                    winners_count = min(len(users), winners)
                    winner_ids = random.sample(users, k=winners_count)
                    winner_mentions = ', '.join(f'<@!{id}>' for id in winner_ids)
                    embed = discord.Embed(
                        title=f"{prize}",
                        description=f"Ended at <t:{int(datetime.datetime.now().timestamp())}:R>\nHosted by <@{host_id}>\nWinner(s): {winner_mentions}",
                        color=0x00FFFF
                    )
                    embed.timestamp = discord.utils.utcnow()
                    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1267699529130709075.png")
                    embed.set_footer(text="Ended at")
                    await message.edit(content="<a:gifts:1346048164955947020> **GIVEAWAY ENDED**<a:gifts:1346048164955947020>", embed=embed)
                    await message.reply(f"<a:giveaway:1345982612241649736> Congrats {winner_mentions}, you won **{prize}!** Hosted by <@{host_id}>")
            except discord.NotFound:
                logging.error(f"Message {message_id} not found in channel {channel_id}")
            except discord.HTTPException as e:
                logging.error(f"Failed to end giveaway {message_id}: {e}")
            finally:
                await self.delete_giveaway(guild_id, message_id)
        except Exception as e:
            logging.error(f"Unexpected error ending giveaway {message_id}: {e}")
            await self.delete_giveaway(guild_id, message_id)

    async def delete_giveaway(self, guild_id, message_id):
        """Remove a giveaway from the database."""
        await self.cursor.execute("DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?", (message_id, guild_id))
        await self.connection.commit()

    ### Commands
    @commands.hybrid_command(description="Starts a new giveaway.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_guild_permissions(manage_guild=True)
    async def gstart(self, ctx, time: str, winners: int, *, prize: str):
        """Start a new giveaway with specified duration, winners, and prize."""
        if winners > 15 or winners < 1:
            embed = discord.Embed(title="❌ Error", description="Number of winners must be between 1 and 15.", color=0xFF0000)
            return await ctx.send(embed=embed, delete_after=5)

        converted = convert(time)
        if converted < 0:
            error_msg = {
                -1: "Invalid time unit. Use s, m, h, or d.",
                -2: "Time must be a positive number.",
                -3: "Time must be a valid number."
            }.get(converted, "Invalid time format.")
            embed = discord.Embed(title="❌ Error", description=error_msg, color=0xFF0000)
            return await ctx.send(embed=embed, delete_after=5)

        if converted > 31 * 86400:  # 31 days in seconds
            embed = discord.Embed(title="❌ Error", description="Giveaway duration cannot exceed 31 days.", color=0xFF0000)
            return await ctx.send(embed=embed, delete_after=5)

        ends_at = datetime.datetime.now().timestamp() + converted
        embed = discord.Embed(
            title=f"🎉 {prize}",
            description=f"Winner(s): **{winners}**\nReact with <a:giveaway:1345982612241649736> to participate!\nEnds <t:{int(ends_at)}:R> (<t:{int(ends_at)}:f>)\nHosted by {ctx.author.mention}",
            color=0x00FFFF
        )
        embed.timestamp = datetime.datetime.fromtimestamp(ends_at, tz=datetime.timezone.utc)
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1267699441394126940.png")
        embed.set_footer(text="Ends at", icon_url=self.bot.user.avatar.url)

        message = await ctx.send("<a:gifts:1346048164955947020> **GIVEAWAY**<a:gifts:1346048164955947020>", embed=embed)
        await message.add_reaction("<a:giveaway:1345982612241649736>")

        await self.cursor.execute(
            "INSERT INTO Giveaway(guild_id, host_id, start_time, ends_at, prize, winners, message_id, channel_id) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (ctx.guild.id, ctx.author.id, datetime.datetime.now().timestamp(), ends_at, prize, winners, message.id, ctx.channel.id)
        )
        await self.connection.commit()

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            logging.warning(f"Could not delete command message in guild {ctx.guild.id}")

    @commands.hybrid_command(name="gend", description="Ends a giveaway early.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_guild_permissions(manage_guild=True)
    async def gend(self, ctx, message_id: int = None):
        """End a giveaway manually by message ID or reply."""
        if not message_id and not ctx.message.reference:
            return await ctx.send("Please provide a message ID or reply to a giveaway message.", delete_after=5)

        target_id = message_id or (ctx.message.reference.resolved.id if ctx.message.reference else None)
        await self.cursor.execute("SELECT ends_at, guild_id, message_id, host_id, winners, prize, channel_id FROM Giveaway WHERE message_id = ?", (target_id,))
        giveaway = await self.cursor.fetchone()

        if not giveaway:
            return await ctx.send("No active giveaway found with that message ID.", delete_after=5)

        await self.end_giveaway(giveaway)
        await ctx.send(f"✅ Giveaway ended successfully.", delete_after=5)

    @commands.hybrid_command(name="greroll", description="Rerolls winners for an ended giveaway.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_guild_permissions(manage_guild=True)
    async def greroll(self, ctx, message_id: int = None):
        """Reroll winners for an ended giveaway."""
        if not message_id and not ctx.message.reference:
            return await ctx.send("Please provide a message ID or reply to an ended giveaway message.", delete_after=5)

        target_id = message_id or (ctx.message.reference.resolved.id if ctx.message.reference else None)
        message = await ctx.channel.fetch_message(target_id)

        if message.author.id != self.bot.user.id:
            return await ctx.send("That message is not a giveaway message.", delete_after=5)

        await self.cursor.execute("SELECT message_id FROM Giveaway WHERE message_id = ?", (target_id,))
        if await self.cursor.fetchone():
            return await ctx.send("This giveaway is still active. Use `gend` to end it first.", delete_after=5)

        users = [user.id async for user in message.reactions[0].users() if user.id != self.bot.user.id]
        if not users:
            return await ctx.send("No participants to reroll.", delete_after=5)

        winners = random.sample(users, k=1)
        winner_mentions = ', '.join(f'<@!{id}>' for id in winners)
        await message.reply(f"<a:giveaway:1345982612241649736> New winner: {winner_mentions}. Congratulations!")
        await ctx.send("✅ Giveaway rerolled successfully.", delete_after=5)

    @commands.hybrid_command(name="glist", description="Lists all ongoing giveaways.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_guild_permissions(manage_guild=True)
    async def glist(self, ctx):
        """List all ongoing giveaways in the guild."""
        await self.cursor.execute("SELECT prize, ends_at, winners, message_id FROM Giveaway WHERE guild_id = ?", (ctx.guild.id,))
        giveaways = await self.cursor.fetchall()

        if not giveaways:
            return await ctx.send(embed=discord.Embed(description="No ongoing giveaways.", color=0x00FFFF))

        embed = discord.Embed(title="Ongoing Giveaways", color=0x00FFFF)
        for prize, ends_at, winners, message_id in giveaways:
            embed.add_field(
                name=prize,
                value=f"Ends: <t:{int(ends_at)}:R> (<t:{int(ends_at)}:f>)\nWinners: {winners}\n[Jump to Message](https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{message_id})",
                inline=False
            )
        await ctx.send(embed=embed)

    ### Event Listeners
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Remove giveaway from database if its message is deleted."""
        if message.author.id != self.bot.user.id:
            return
        await self.cursor.execute("DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?", (message.id, message.guild.id))
        await self.connection.commit()
        logging.info(f"Giveaway message {message.id} deleted in guild {message.guild.id}")

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
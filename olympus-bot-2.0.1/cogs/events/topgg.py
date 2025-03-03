import discord
from discord.ext import commands
import topgg
import datetime
import aiosqlite

class TopGG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjExNDQxNzk2NTk3MzU1NzI2NDAiLCJib3QiOnRydWUsImlhdCI6MTczMTk5NDQyOH0.6UIanXSCeA5EINNcvat9NTPYmWM5k9nvxXLxxbmPoqI"
        self.auth = "odx69"
        self.topgg_client = topgg.DBLClient(self.bot, self.token, autopost=True)
        self.webhook_manager = topgg.WebhookManager(self.bot).dbl_webhook("/topggwebhook", self.auth)
        self.bot.loop.create_task(self._init_db())
        self.webhook_manager.run(2022)

    async def _init_db(self):
        self.db = await aiosqlite.connect("db/topgg.db")
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                user_id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0
            )
        """)
        await self.db.commit()

    async def _get_vote_data(self, user_id):
        async with self.db.execute("SELECT count, streak FROM votes WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0], row[1]) if row else (0, 0)

    async def _update_vote_data(self, user_id, new_count, new_streak):
        await self.db.execute("""
            INSERT INTO votes (user_id, count, streak)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            count = excluded.count,
            streak = excluded.streak
        """, (user_id, new_count, new_streak))
        await self.db.commit()

    @commands.Cog.listener()
    async def on_dbl_vote(self, data):
        user_id = int(data["user"])
        user = await self.bot.fetch_user(user_id)
        current_count, current_streak = await self._get_vote_data(user_id)
        new_count = current_count + 1
        new_streak = current_streak + 1
        await self._update_vote_data(user_id, new_count, new_streak)
        embed = discord.Embed(title="<a:iconOnline:1219295650605174878> [Voted](https://top.gg/bot/1144179659735572640/vote)", color=0xff0000)
        next_vote_time = datetime.datetime.now() + datetime.timedelta(hours=12)
        embed.add_field(name="<:clock:1204234343552385095> Can vote again at:", value=f"<t:{int(next_vote_time.timestamp())}:R>", inline=False)
        embed.add_field(name="<:config:1205442007724466226> Total Votes:", value=str(new_count), inline=False)
        embed.add_field(name="<:daily:1206601095066165310> Current Vote Streak:", value=str(new_streak), inline=False)
        embed.timestamp = datetime.datetime.now()
        channel = self.bot.get_channel(1257877889425215519)
        await channel.send(f"{user.mention} Voted for {self.bot.user.mention}!", embed=embed)

async def setup(bot):
    await bot.add_cog(TopGG(bot))

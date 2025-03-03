import discord
import asyncio
import yt_dlp
from discord.ext import commands
from discord.ui import Button, View
from datetime import datetime
import aiosqlite

yt_dl_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'ignoreerrors': True
}
ytdl = yt_dlp.YoutubeDL(yt_dl_options)

ffmpeg_options = {
    'executable': 'ffmpeg',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.25"'
}

class MusicPlayer:
    def __init__(self, guild_id, cog):
        self.guild_id = guild_id
        self.cog = cog
        self.bot = cog.bot
        self.queue = []
        self.current_song = None
        self.voice_client = None
        self.text_channel = None
        self.loop = False
        self.message = None

    async def add_to_queue(self, song):
        self.queue.append(song)
        if not self.is_playing():
            await self.play_next()

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    async def play_next(self):
        if not self.voice_client or not self.voice_client.is_connected():
            return

        if len(self.queue) == 0 and not self.loop:
            embed = discord.Embed(
                title="Queue Empty",
                description="Disconnecting from voice channel...",
                color=0xff0000
            )
            await self.text_channel.send(embed=embed)
            await self.cleanup()
            return

        if self.loop and self.current_song:
            self.queue.insert(0, self.current_song)

        try:
            self.current_song = self.queue.pop(0)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(
                self.current_song['url'], download=False))

            if 'entries' in data and len(data['entries']) > 0:
                data = data['entries'][0]
            elif 'url' not in data:
                embed = discord.Embed(
                    title="Playback Error",
                    description="No valid audio found for playback",
                    color=0xff0000
                )
                await self.text_channel.send(embed=embed)
                await self.play_next()
                return

            source = data.get('url')
            audio_source = discord.FFmpegOpusAudio(source, **ffmpeg_options)

            self.voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(
                self.play_next(), self.bot.loop))

            await self.update_controller()

        except Exception as e:
            print(f"Error in play_next: {e}")
            embed = discord.Embed(
                title="Playback Error",
                description="Error playing song, skipping to next...",
                color=0xff0000
            )
            await self.text_channel.send(embed=embed)
            await self.play_next()

    async def update_controller(self):
        embed = discord.Embed(
            title="Now Playing",
            description=f"**{self.current_song['title']}**",
            color=0x00ff00
        )
        embed.set_footer(text=f"Requested by {self.current_song['requester']}")

        if self.message:
            try:
                await self.message.edit(embed=embed, view=MusicController(self))
            except discord.NotFound:
                self.message = None
        if not self.message and self.text_channel:
            self.message = await self.text_channel.send(embed=embed, view=MusicController(self))

    async def cleanup(self):
        if self.voice_client:
            await self.voice_client.disconnect()
        if self.message:
            try:
                await self.message.delete()
            except discord.NotFound:
                pass
        if self.guild_id in self.cog.music_players:
            del self.cog.music_players[self.guild_id]

class MusicController(View):
    def __init__(self, music_player):
        super().__init__(timeout=180)
        self.music_player = music_player
        self.set_button_states()

    def set_button_states(self):
        for child in self.children:
            if child.custom_id == "play_pause":
                if self.music_player.voice_client.is_playing():
                    child.label = "Pause"
                    child.emoji = "⏸"
                elif self.music_player.voice_client.is_paused():
                    child.label = "Resume"
                    child.emoji = "▶"
                else:
                    child.label = "Play"
                    child.emoji = "⏯"

    @discord.ui.button(label="Play/Pause", style=discord.ButtonStyle.primary, emoji="⏯", custom_id="play_pause")
    async def play_pause(self, interaction, button):
        if self.music_player.voice_client.is_playing():
            self.music_player.voice_client.pause()
            button.label = "Resume"
            button.emoji = "▶"
        elif self.music_player.voice_client.is_paused():
            self.music_player.voice_client.resume()
            button.label = "Pause"
            button.emoji = "⏸"
        else:
            await self.music_player.play_next()

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭")
    async def skip(self, interaction, button):
        self.music_player.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹")
    async def stop(self, interaction, button):
        await self.music_player.cleanup()
        await interaction.response.defer()

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.green, emoji="📋")
    async def show_queue(self, interaction, button):
        queue_list = "\n".join(
            [f"{i+1}. {song['title']}" for i, song in enumerate(self.music_player.queue)])
        
        embed = discord.Embed(
            title="Music Queue",
            description=queue_list or "No songs in queue",
            color=0x00ff00
        )
        embed.set_footer(text=f"Total songs in queue: {len(self.music_player.queue)}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except discord.NotFound:
            pass

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_players = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id and before.channel and not after.channel:
            if member.guild.id in self.music_players:
                await self.music_players[member.guild.id].cleanup()
    async def ensure_db(self):
        """Ensures the database and table exist."""
        async with aiosqlite.connect("vc_247.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vc_status (
                    guild_id INTEGER PRIMARY KEY,
                    voice_channel_id INTEGER,
                    enabled INTEGER
                )
            """
            )
            await db.commit()
    @commands.command(name="247")
    @commands.has_permissions(manage_guild=True)
    async def toggle_vc_247(self, ctx):
        """Toggles 24/7 VC mode for the guild."""
        await self.ensure_db()
        guild_id = ctx.guild.id
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None
        
        if not voice_channel:
            embed = discord.Embed(
                title="Error",
                description="You must be in a voice channel to toggle 24/7 mode!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        async with aiosqlite.connect("vc_247.db") as db:
            async with db.execute("SELECT enabled FROM vc_status WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] == 1:  # If already enabled, disable it
                    await db.execute("UPDATE vc_status SET enabled = 0 WHERE guild_id = ?", (guild_id,))
                    await db.commit()
                    if ctx.guild.voice_client:
                        await ctx.guild.voice_client.disconnect()
                    embed = discord.Embed(
                        title="24/7 VC Disabled",
                        description="The bot has left the voice channel.",
                        color=discord.Color.red()
                    )
                else:  # If disabled, enable it
                    await db.execute("REPLACE INTO vc_status (guild_id, voice_channel_id, enabled) VALUES (?, ?, 1)", (guild_id, voice_channel.id))
                    await db.commit()
                    await voice_channel.connect()
                    embed = discord.Embed(
                        title="24/7 VC Enabled",
                        description=f"The bot has joined {voice_channel.mention}.",
                        color=discord.Color.green()
                    )
        await ctx.send(embed=embed)

    @toggle_vc_247.error
    async def toggle_vc_247_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="Permission Denied",
                description="You need the **Manage Guild** permission to use this command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def play(self, ctx, *, query: str):
        try:
            if not ctx.author.voice:
                embed = discord.Embed(
                    title="Voice Channel Required",
                    description="You need to be in a voice channel to use this command!",
                    color=0xff0000
                )
                await ctx.send(embed=embed)
                return

            if ctx.guild.id not in self.music_players:
                self.music_players[ctx.guild.id] = MusicPlayer(ctx.guild.id, self)
            
            player = self.music_players[ctx.guild.id]
            player.text_channel = ctx.channel

            if not player.voice_client or not player.voice_client.is_connected():
                player.voice_client = await ctx.author.voice.channel.connect()
                
            embed1 = discord.Embed(
                    title="Music Serching",
                    description="Finding music....",
                    color=0xff0000
                )
            await ctx.send(embed=embed1)    

            data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ytdl.extract_info(f"ytsearch:{query}", download=False))

            if not data or 'entries' not in data or not data['entries']:
                embed = discord.Embed(
                    title="No Results",
                    description="No results found for your search query",
                    color=0xff0000
                )
                await embed1.edit(embed=embed)
                return

            song = {
                'title': data['entries'][0]['title'],
                'url': data['entries'][0]['url'],
                'requester': ctx.author.display_name
            }

            await player.add_to_queue(song)
            
            embed = discord.Embed(
                title="Song Added to Queue",
                description=f"**{song['title']}** has been added to the queue",
                color=0x00ff00
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Play command error: {e}")
            embed = discord.Embed(
                title="Command Error",
                description="An error occurred while processing your request",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def leave(self, ctx):
        if ctx.guild.id in self.music_players:
            await self.music_players[ctx.guild.id].cleanup()
            embed = discord.Embed(
                title="Disconnected",
                description="Left the voice channel",
                color=0x00ff00
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))
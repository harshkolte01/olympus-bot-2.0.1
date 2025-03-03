import discord
from discord.ext import commands
import aiosqlite
import asyncio
from discord.ui import Select, View, Modal, TextInput

# Default limits for anti-nuke actions
DEFAULT_LIMITS = {
    'ban': 1,
    'channel_create': 1,
    'channel_delete': 3,
    'channel_update': 6,
    'guild_update': 2,
    'kick': 4,
    'member_update': 6,
    'mention': 6,
    'role_create': 3,
    'role_delete': 2,
    'role_update': 3,
    'timeout': 8,
    'webhook_create': 4,
    'webhook_delete': 3
}
TIME_WINDOW = 600  # 10 minutes in seconds

class Antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
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

    async def get_limit(self, guild_id, action_type):
        """Get the limit for a specific action type in a guild."""
        async with self.db.execute('''
            SELECT action_limit FROM limit_settings
            WHERE guild_id = ? AND action_type = ?
        ''', (guild_id, action_type)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else DEFAULT_LIMITS.get(action_type, 0)

    @commands.hybrid_group(name='antinuke', aliases=['antiwizz', 'anti'], help="Manage the Anti-Nuke system.")
    async def antinuke(self, ctx):
        """Base command for Anti-Nuke configuration."""
        if ctx.invoked_subcommand is None:
            pre = ctx.prefix
            embed = discord.Embed(
                title='Antinuke Protection',
                description="Configure server-wide protection against malicious actions.",
                color=0x00FFFF
            )
            embed.add_field(name="Enable", value=f"{pre}antinuke enable - Activate security modules")
            embed.add_field(name="Disable", value=f"{pre}antinuke disable - Deactivate all protections")
            embed.add_field(name="Settings", value=f"{pre}antinuke settings - View current configuration")
            embed.add_field(name="Configure", value=f"{pre}antinuke set - Adjust module thresholds")
            embed.add_field(name="Set Log Channel", value=f"{pre}antinuke logchannel <#channel> - Set logging channel")
            await ctx.send(embed=embed)

    @antinuke.command(name='enable')
    @commands.has_permissions(administrator=True)
    async def enable(self, ctx):
        """Enable Anti-Nuke protection for the server."""
        guild_id = ctx.guild.id
        await self.db.execute('INSERT OR REPLACE INTO antinuke (guild_id, status) VALUES (?, ?)', (guild_id, True))
        await self.db.commit()
        await ctx.send("✅ Anti-Nuke has been enabled.")

    @antinuke.command(name='disable')
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        """Disable Anti-Nuke protection for the server."""
        guild_id = ctx.guild.id
        await self.db.execute('DELETE FROM antinuke WHERE guild_id = ?', (guild_id,))
        await self.db.execute('DELETE FROM limit_settings WHERE guild_id = ?', (guild_id,))
        await self.db.execute('DELETE FROM antinuke_logging WHERE guild_id = ?', (guild_id,))
        await self.db.commit()
        await ctx.send("❌ Anti-Nuke has been disabled and all settings have been cleared.")

    @antinuke.command(name='settings')
    async def settings(self, ctx):
        """View the current Anti-Nuke configuration."""
        guild_id = ctx.guild.id
        async with self.db.execute('SELECT status FROM antinuke WHERE guild_id = ?', (guild_id,)) as cursor:
            status = await cursor.fetchone()
        
        if not status or not status[0]:
            return await ctx.send("❌ Anti-Nuke is not enabled!")
        
        limits = {}
        for action in DEFAULT_LIMITS:
            limit = await self.get_limit(guild_id, action)
            limits[action] = limit
        
        log_channel = None
        async with self.db.execute('SELECT log_channel FROM antinuke_logging WHERE guild_id = ?', (guild_id,)) as cursor:
            channel_id = await cursor.fetchone()
            if channel_id:
                log_channel = ctx.guild.get_channel(channel_id[0])
        
        embed = discord.Embed(title="Anti-Nuke Configuration", color=0x00FFFF)
        for action, limit in limits.items():
            name = action.replace('_', ' ').title()
            embed.add_field(name=f"❯ *{name}*", value=f"Limit: {limit}", inline=False)
        
        embed.add_field(name="Logging Channel", value=log_channel.mention if log_channel else "Not Set", inline=False)
        embed.add_field(name="Time Window", value="10 Minutes (Unchangeable)", inline=False)
        await ctx.send(embed=embed)

    @antinuke.command(name='set')
    @commands.has_permissions(administrator=True)
    async def set_limit(self, ctx):
        """Set custom limits for Anti-Nuke actions."""
        class LimitModal(Modal, title="Configure Action Limit"):
            def __init__(self, action, current_limit):
                super().__init__()
                self.action = action
                self.add_item(TextInput(label="New Limit", default=str(current_limit)))

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    new_limit = int(self.children[0].value)
                except ValueError:
                    return await interaction.response.send_message("❌ Invalid number! Please enter a valid integer.", ephemeral=True)
                
                await self.cog.db.execute('''
                    INSERT OR REPLACE INTO limit_settings 
                    (guild_id, action_type, action_limit, time_window)
                    VALUES (?, ?, ?, ?)
                ''', (interaction.guild.id, self.action, new_limit, TIME_WINDOW))
                await self.cog.db.commit()
                await interaction.response.send_message(f"✅ Updated limit for `{self.action.replace('_', ' ').title()}` to `{new_limit}`!", ephemeral=True)

        select = Select(placeholder="Select module to configure...")
        for action in DEFAULT_LIMITS:
            select.add_option(label=action.replace('_', ' ').title(), value=action)
        
        async def select_callback(interaction):
            action = select.values[0]
            current_limit = await self.get_limit(ctx.guild.id, action)
            modal = LimitModal(action, current_limit)
            modal.cog = self
            await interaction.response.send_modal(modal)
        
        select.callback = select_callback
        view = View()
        view.add_item(select)
        await ctx.send("Choose a module to adjust:", view=view)

    @antinuke.command(name='logchannel')
    @commands.has_permissions(administrator=True)
    async def set_log(self, ctx, channel: discord.TextChannel):
        """Set the logging channel for Anti-Nuke actions."""
        guild_id = ctx.guild.id
        await self.db.execute('INSERT OR REPLACE INTO antinuke_logging VALUES (?, ?)', (guild_id, channel.id))
        await self.db.commit()
        await ctx.send(f"✅ Log channel set to {channel.mention}")

    # Error Handling
    @enable.error
    @disable.error
    @set_limit.error
    @set_log.error
    async def antinuke_error(self, ctx, error):
        """Handle errors for Anti-Nuke commands."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permissions to use this command!")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided. Please check your input.")
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}")

async def setup(bot):
    await bot.add_cog(Antinuke(bot))
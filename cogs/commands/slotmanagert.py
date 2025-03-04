import discord
from discord.ext import commands
import aiosqlite
from discord import ui
from discord.ui import View, Select, Button
import asyncio

class SlotManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "tournament.db"  # Path to your SQLite database

    @commands.command(name="slotmanager")
    async def slotmanager(self, ctx):
        """Initiates the slot manager by showing available tournaments."""
        # Fetch tournaments for the guild
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT tournament_no FROM tournaments WHERE guild_id = ?", (ctx.guild.id,))
            tournaments = await cursor.fetchall()

        if not tournaments:
            await ctx.send("No tournaments found for this server.")
            return

        # Create select options for each tournament
        options = [discord.SelectOption(label=f"Tournament {t[0]}", value=str(t[0])) for t in tournaments]

        # Create the select menu
        select = Select(placeholder="Select a tournament", options=options)

        async def select_callback(interaction):
            """Handles tournament selection and prompts for a channel."""
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command initiator can select a tournament.", ephemeral=True)
                return
            selected_tournament_no = int(select.values[0])
            view.selected_tournament_no = selected_tournament_no
            await interaction.response.send_message("Please mention the channel where you want the slot manager sent (e.g., #channel).", ephemeral=True)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and len(m.channel_mentions) > 0

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
                channel = msg.channel_mentions[0]
                await self.send_slot_manager_embed(channel, ctx.author, selected_tournament_no)
            except asyncio.TimeoutError:
                await ctx.send("You took too long to mention a channel.")

        select.callback = select_callback

        view = View()
        view.add_item(select)
        view.selected_tournament_no = None  # To store the selected tournament number

        await ctx.send("Please select a tournament:", view=view)

    async def send_slot_manager_embed(self, channel, user, tournament_no):
        """Sends the slot manager embed with buttons to the specified channel."""
        embed = discord.Embed(title=f"Slot Manager - Tournament {tournament_no}", color=discord.Color.blue())
        embed.set_footer(text="Use the buttons below to manage your slot.")

        view = SlotManagerView(self.bot, self.db_path, user, tournament_no)
        await channel.send(embed=embed, view=view)

class SlotManagerView(View):
    def __init__(self, bot, db_path, user, tournament_no):
        super().__init__(timeout=300)  # 5-minute timeout
        self.bot = bot
        self.db_path = db_path
        self.user = user
        self.tournament_no = tournament_no

    @discord.ui.button(label="Show Slot", style=discord.ButtonStyle.primary)
    async def show_slot(self, interaction: discord.Interaction, button: Button):
        """Displays the user's team slot details if registered."""
        if interaction.user != self.user:
            await interaction.response.send_message("Only the slot manager initiator can use this button.", ephemeral=True)
            return

        # Check if the user is a captain in the tournament
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM teams WHERE guild_id = ? AND tournament_no = ? AND captain_id = ?",
                (interaction.guild.id, self.tournament_no, self.user.id)
            )
            team = await cursor.fetchone()

        if not team:
            await interaction.response.send_message("You are not registered in this tournament.", ephemeral=True)
            return

        # Calculate slot number based on registration order (id)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id FROM teams WHERE guild_id = ? AND tournament_no = ? ORDER BY id",
                (interaction.guild.id, self.tournament_no)
            )
            teams = await cursor.fetchall()
        slot_number = next((index + 1 for index, t in enumerate(teams) if t[0] == team[0]), None)

        # Parse members (assumed to be comma-separated IDs)
        members = team[5].split(',')

        # Create embed with team details
        embed = discord.Embed(title=f"Team {team[3]} - Slot {slot_number}", color=discord.Color.green())
        embed.add_field(name="Team Name", value=team[3], inline=False)
        embed.add_field(name="Captain", value=f"<@{team[4]}>", inline=False)
        embed.add_field(name="Members", value=", ".join(f"<@{m}>" for m in members), inline=False)
        embed.add_field(name="Confirmed", value="Yes" if team[6] else "No", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Cancel Slot", style=discord.ButtonStyle.danger)
    async def cancel_slot(self, interaction: discord.Interaction, button: Button):
        """Prompts to cancel the user's slot with confirmation."""
        if interaction.user != self.user:
            await interaction.response.send_message("Only the slot manager initiator can use this button.", ephemeral=True)
            return

        # Check registration
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM teams WHERE guild_id = ? AND tournament_no = ? AND captain_id = ?",
                (interaction.guild.id, self.tournament_no, self.user.id)
            )
            team = await cursor.fetchone()

        if not team:
            await interaction.response.send_message("You are not registered in this tournament.", ephemeral=True)
            return

        # Send confirmation embed
        embed = discord.Embed(
            title="Confirm Cancellation",
            description="Are you sure you want to cancel your slot? This action cannot be undone.",
            color=discord.Color.red()
        )
        view = ConfirmCancelView(self.bot, self.db_path, self.user, self.tournament_no, team[0])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Change Team Name", style=discord.ButtonStyle.secondary)
    async def change_team_name(self, interaction: discord.Interaction, button: Button):
        """Prompts the user to change their team name."""
        if interaction.user != self.user:
            await interaction.response.send_message("Only the slot manager initiator can use this button.", ephemeral=True)
            return

        # Check registration
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM teams WHERE guild_id = ? AND tournament_no = ? AND captain_id = ?",
                (interaction.guild.id, self.tournament_no, self.user.id)
            )
            team = await cursor.fetchone()

        if not team:
            await interaction.response.send_message("You are not registered in this tournament.", ephemeral=True)
            return

        await interaction.response.send_message("Please enter the new team name:", ephemeral=True)

        def check(m):
            return m.author == self.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            new_team_name = msg.content.strip()
            if not new_team_name:
                await interaction.followup.send("Team name cannot be empty.", ephemeral=True)
                return

            # Update team name in the database
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE teams SET team_name = ? WHERE id = ?",
                    (new_team_name, team[0])
                )
                await db.commit()

            await interaction.followup.send(f"Team name updated to '{new_team_name}'.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to respond.", ephemeral=True)

class ConfirmCancelView(View):
    def __init__(self, bot, db_path, user, tournament_no, team_id):
        super().__init__(timeout=60)  # 1-minute timeout
        self.bot = bot
        self.db_path = db_path
        self.user = user
        self.tournament_no = tournament_no
        self.team_id = team_id

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def confirm_cancel(self, interaction: discord.Interaction, button: Button):
        """Confirms slot cancellation and removes team data."""
        if interaction.user != self.user:
            await interaction.response.send_message("Only the slot manager initiator can confirm this.", ephemeral=True)
            return

        # Remove team and update slots_filled
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM teams WHERE id = ?", (self.team_id,))
            await db.execute(
                "UPDATE tournaments SET slots_filled = slots_filled - 1 WHERE guild_id = ? AND tournament_no = ?",
                (interaction.guild.id, self.tournament_no)
            )
            await db.commit()

        await interaction.response.send_message("Your slot has been cancelled.", ephemeral=True)

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def cancel_cancel(self, interaction: discord.Interaction, button: Button):
        """Aborts the cancellation process."""
        if interaction.user != self.user:
            await interaction.response.send_message("Only the slot manager initiator can cancel this.", ephemeral=True)
            return
        await interaction.response.send_message("Cancellation aborted.", ephemeral=True)

async def setup(bot):
    """Loads the SlotManager cog into the bot."""
    await bot.add_cog(SlotManager(bot))
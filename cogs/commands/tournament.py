import discord
from discord.ext import commands
import aiosqlite
from discord import ui
from discord.ui import View, Modal, Button, TextInput
import asyncio

class Tournament(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "tournament.db"  # SQLite database file path

    async def init_db(self):
        """Initialize the SQLite database with required tables."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tournaments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    tournament_no INTEGER,
                    reg_channel INTEGER,
                    confirm_channel INTEGER,
                    success_role INTEGER,
                    required_mentions INTEGER,
                    total_slots INTEGER,
                    slots_filled INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    tournament_no INTEGER,
                    team_name TEXT,
                    captain_id INTEGER,
                    members TEXT,
                    confirmed INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ignored_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    role_id INTEGER,
                    role_name TEXT
                )
            """)
            await db.commit()

    async def get_guild_data(self, guild_id):
        """Fetch guild-specific tournament data."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM tournaments WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchone()

    @commands.command(name="ignorerole")
    @commands.has_permissions(administrator=True)
    async def ignorerole(self, ctx, role: discord.Role):
        """Command to ignore a role by adding it to the database."""
        guild_id = ctx.guild.id
        role_id = role.id

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM ignored_roles WHERE guild_id = ? AND role_id = ?",
                (guild_id, role_id)
            )
            existing_role = await cursor.fetchone()
            if existing_role:
                await ctx.send(f"Role `{role.name}` is already being ignored.")
                return

            await db.execute(
                "INSERT INTO ignored_roles (guild_id, role_id, role_name) VALUES (?, ?, ?)",
                (guild_id, role_id, role.name)
            )
            await db.commit()

        await ctx.send(f"Role `{role.name}` has been added to the ignored roles list.")

    @commands.command(name="delete_cr")
    @commands.has_permissions(manage_channels=True, manage_roles=True)
    async def delete_cr(self, ctx, category_name_or_id: str):
        """Deletes all channels under a category and removes matching roles."""
        guild = ctx.guild
        category = None

        if category_name_or_id.isdigit():
            category = discord.utils.get(guild.categories, id=int(category_name_or_id))
        else:
            category = discord.utils.get(guild.categories, name=category_name_or_id)

        if not category:
            return await ctx.send("❌ Category not found.")

        embed = discord.Embed(
            title="Deleting Category and Associated Channels/Roles",
            description=f"**Category:** {category.name}\n**Channels to be deleted:** {len(category.channels)}\n**Roles to be deleted:** {len(category.channels)}",
            color=0xff0000
        )
        await ctx.send(embed=embed)

        channels_to_delete = category.channels
        role_names_to_delete = [channel.name for channel in channels_to_delete]
        roles_to_delete = [discord.utils.get(guild.roles, name=role_name) for role_name in role_names_to_delete]

        for channel in channels_to_delete:
            await channel.delete()

        for role in roles_to_delete:
            if role:
                await role.delete()

        try:
            await category.delete()
            await ctx.send(f"✅ Successfully deleted category `{category.name}` and all associated channels/roles.")
        except discord.Forbidden as e:
            print(f"Bot is not allowed to delete the category {category.name}: {e}")
            await ctx.send(f"❌ Bot does not have the necessary permissions to delete the category `{category.name}`.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def tournament(self, ctx):
        """Main tournament management command."""
        await self.init_db()  # Ensure database is initialized
        embed = discord.Embed(title="Tournament Manager", color=0x00ff00)
        view = MainDashboardView(self.bot, self.db_path)
        await ctx.send(embed=embed, view=view)
        print(f"Tournament command executed in guild: {ctx.guild.name}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle team registration via messages."""
        if message.author.bot or not message.guild:
            return

        guild_data = await self.get_guild_data(message.guild.id)
        if not guild_data:
            return

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT role_id FROM ignored_roles WHERE guild_id = ?",
                (message.guild.id,)
            )
            ignored_roles = [row[0] for row in await cursor.fetchall()]

        if any(role.id in ignored_roles for role in message.author.roles):
            return

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM tournaments WHERE guild_id = ? AND reg_channel = ?",
                (message.guild.id, message.channel.id)
            )
            tournament = await cursor.fetchone()

        if not tournament:
            return

        tournament_no = tournament[2]  # tournament_no is the third column
        guild_id = message.guild.id
        captain_id = message.author.id

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM teams WHERE guild_id = ? AND tournament_no = ? AND captain_id = ?",
                (guild_id, tournament_no, captain_id)
            )
            existing_team = await cursor.fetchone()

        try:
            content = message.content.strip().split('\n')
            if len(content) < 1:
                raise ValueError("Invalid format! Use: Team Name\n@member1 @member2")

            team_name = content[0].strip()
            mentions = message.mentions

            if existing_team:
                raise ValueError("❌ You are already registered in this tournament!")

            required_mentions = tournament[6]  # required_mentions is the seventh column
            if len(mentions) < required_mentions:
                raise ValueError(f"Need at least {required_mentions} team members mentioned!")

            if not team_name.lower().startswith("team"):
                raise ValueError("Team name must start with 'Team'!")

            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT * FROM teams WHERE guild_id = ? AND tournament_no = ? AND team_name = ?",
                    (guild_id, tournament_no, team_name)
                )
                existing_team_name = await cursor.fetchone()
                if existing_team_name:
                    raise ValueError("Team name already exists!")

                await db.execute(
                    "INSERT INTO teams (guild_id, tournament_no, team_name, captain_id, members, confirmed) VALUES (?, ?, ?, ?, ?, ?)",
                    (guild_id, tournament_no, team_name, captain_id, ','.join(str(m.id) for m in mentions), 1)
                )
                await db.execute(
                    "UPDATE tournaments SET slots_filled = slots_filled + 1 WHERE guild_id = ? AND tournament_no = ?",
                    (guild_id, tournament_no)
                )
                await db.commit()

            success_role = message.guild.get_role(tournament[5])  # success_role is the sixth column
            if success_role:
                for member in [message.author] + mentions:
                    await member.add_roles(success_role)

            confirm_channel = self.bot.get_channel(tournament[4])  # confirm_channel is the fifth column
            if confirm_channel:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(
                        "SELECT * FROM teams WHERE guild_id = ? AND tournament_no = ? AND confirmed = ?",
                        (guild_id, tournament_no, 1)
                    )
                    confirmed_teams = await cursor.fetchall()

                description = [
                    f"{idx+1}. **{team[3]}**\nPlayers: {', '.join(f'<@{m}>' for m in team[5].split(','))}\nCaptain: <@{team[4]}>"
                    for idx, team in enumerate(confirmed_teams)
                ]

                embed = discord.Embed(
                    title=f"Confirmed Teams - Tournament {tournament_no}",
                    description='\n\n'.join(description),
                    color=0x00ff00
                )
                await confirm_channel.send(embed=embed)

            await message.add_reaction('✅')

            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT slots_filled, total_slots FROM tournaments WHERE guild_id = ? AND tournament_no = ?",
                    (guild_id, tournament_no)
                )
                tournament_data = await cursor.fetchone()
                if tournament_data[0] >= tournament_data[1]:
                    embed = discord.Embed(
                        title="All Slots Are Full",
                        description=f"Registration for Tournament {tournament_no} is now closed!",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed)
                    await message.channel.set_permissions(message.guild.default_role, send_messages=False)

        except Exception as e:
            embed = discord.Embed(
                description=f"{message.author.mention} {str(e)}",
                color=discord.Color.red()
            )
            await message.reply(embed=embed)
            await message.add_reaction('❌')


class MainDashboardView(ui.View):
    def __init__(self, bot, db_path):
        super().__init__(timeout=60)
        self.bot = bot
        self.db_path = db_path

    async def get_tournament(self, guild_id):
        """Fetch tournament details from SQLite."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM tournaments WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchone()

    @discord.ui.button(label="Edit Tournament", style=discord.ButtonStyle.primary, custom_id="edit_tournament")
    async def edit_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Displays tournament settings and allows editing."""
        guild_id = interaction.guild.id
        tournament = await self.get_tournament(guild_id)

        if not tournament:
            return await interaction.response.send_message("❌ No tournament found for this server!", ephemeral=True)

        view = TournamentEditView(self.db_path, guild_id)
        await view.fetch_tournaments()

        if not view.tournaments:
            return await interaction.response.send_message("❌ No tournaments found for this server!", ephemeral=True)

        await view.send_initial_message(interaction)

    @discord.ui.button(label="Show Tournament", style=discord.ButtonStyle.primary)
    async def show_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Displays tournament settings."""
        guild_id = interaction.guild.id
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM tournaments WHERE guild_id = ?", (guild_id,))
            tournaments = await cursor.fetchall()

        if not tournaments:
            return await interaction.response.send_message("❌ No tournament found for this server!", ephemeral=True)

        view = TournamentView(tournaments, self.db_path)
        embed = await view.generate_embed(0)
        await interaction.response.send_message(embed=embed, view=view)

    @ui.button(label="Create Tournament", style=discord.ButtonStyle.blurple)
    async def create_tournament(self, interaction: discord.Interaction, button: ui.Button):
        """Opens a modal for tournament creation."""
        await interaction.response.send_modal(TournamentSetupModal(self.db_path))

    @ui.button(style=discord.ButtonStyle.primary, label="Slot Manager", custom_id="edit_total_slots")
    async def edit_total_slots(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Provides slot management instructions."""
        embed = discord.Embed(
            title="🔹 Slot Manager Guide",
            description="Set up the slot manager using the following methods:\n\n"
                        "**🔹 Use a command:** `!slotmanager`\n"
                        "This command sets the slot manager in a channel.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Tournament Slot Manager | Adjust slots wisely!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(style=discord.ButtonStyle.primary, label="Slot List Manager")
    async def slotlist_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Provides slot list creation guide."""
        embed = discord.Embed(
            title="🔹 Slot List Manager Guide",
            description="Use the following command to create a slot list:\n\n"
                        "`!make_slotlist <each group teams> <total group> <slot list start from>`\n\n"
                        "**Example:** `!make_slotlist 20 2 1`",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Tournament Slot List Manager | Organize wisely!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(style=discord.ButtonStyle.primary, label="Create Channels & Roles")
    async def create_channels_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Provides guidance on creating channels and roles."""
        embed = discord.Embed(
            title="🔹 Channel & Role Creator Guide",
            description="Use the following command to create roles & channels:\n\n"
                        "`!make_cr <channel&role name> <count>`\n\n"
                        "**Example:** `!make_cr bour1g 5`\n"
                        "For more help, use `!help mkar_cr`.",
            color=discord.Color.blue()
        )
        view = StartView(self.db_path)
        embed.set_footer(text="Tournament Groups & Roles Manager | Adjust wisely!")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class StartView(View):
    def __init__(self, db_path):
        super().__init__(timeout=60)
        self.db_path = db_path

    @discord.ui.button(label="Start Creation", style=discord.ButtonStyle.primary)
    async def start_button(self, interaction: discord.Interaction, button: Button):
        """Opens a modal for channel & role creation setup."""
        await interaction.response.send_modal(InputModal(self.db_path))


class InputModal(Modal):
    def __init__(self, db_path):
        super().__init__(title="Channel/Role Creation Setup")
        self.db_path = db_path
        self.channel_input = TextInput(label="Base Channel Name", placeholder="group-chat")
        self.count_input = TextInput(label="Number to Create (1-50)", placeholder="5")
        self.add_item(self.channel_input)
        self.add_item(self.count_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Processes input and initiates creation of channels & roles."""
        try:
            count = int(self.count_input.value)
            base_name = self.channel_input.value.strip()

            if count < 1 or count > 50:
                return await interaction.response.send_message("❌ Please enter a number between 1 and 50.", ephemeral=True)

            await interaction.response.defer()
            embed = discord.Embed(
                title="⏳ Processing Your Request",
                description=f"Creating {count} channels/roles with base name: {base_name}",
                color=discord.Color.orange()
            )
            msg = await interaction.followup.send(embed=embed)
            await self.create_channels_roles(interaction, base_name, count, msg)

        except Exception as e:
            error_embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    async def create_channels_roles(self, interaction, base_name, count, progress_message):
        """Creates roles & channels and stores them in SQLite."""
        try:
            guild = interaction.guild
            category = await guild.create_category(f"{base_name}-category")
            created_channels = []
            created_roles = []

            for i in range(1, count + 1):
                new_role = await guild.create_role(name=f"{base_name}-role-{i}")
                created_roles.append({"name": new_role.name, "id": new_role.id})
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    new_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)
                }
                new_channel = await guild.create_text_channel(
                    name=f"{base_name}-{i}",
                    category=category,
                    overwrites=overwrites
                )
                created_channels.append({"name": new_channel.name, "id": new_channel.id})
                embed = discord.Embed(
                    title=f"📌 Progress: {i}/{count}",
                    description=f"Created: {base_name}-{i}",
                    color=discord.Color.blue()
                )
                await progress_message.edit(embed=embed)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO tournaments (guild_id, tournament_no, reg_channel, confirm_channel, success_role, required_mentions, total_slots, slots_filled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (guild.id, 1, created_channels[0]["id"], created_channels[0]["id"], created_roles[0]["id"], 3, count, 0)
                )
                await db.commit()

            success_embed = discord.Embed(
                title="✅ Creation Complete",
                description=f"Successfully created {count} channels/roles in {category.mention}",
                color=discord.Color.green()
            )
            await progress_message.edit(embed=success_embed)

        except Exception as e:
            error_embed = discord.Embed(title="❌ Creation Failed", description=str(e), color=discord.Color.red())
            await progress_message.edit(embed=error_embed)


class TournamentSetupModal(Modal):
    def __init__(self, db_path):
        super().__init__(title="Tournament Setup", timeout=60)
        self.db_path = db_path
        self.add_item(TextInput(label="Registration Channel ID"))
        self.add_item(TextInput(label="Confirmation Channel ID"))
        self.add_item(TextInput(label="Success Role ID"))
        self.add_item(TextInput(label="Required Mentions", default="3"))
        self.add_item(TextInput(label="Total Slots", placeholder="Enter number of slots"))

    def extract_id(self, value: str) -> int:
        """Extracts an integer ID from user input."""
        try:
            return int(value.strip())
        except ValueError:
            raise ValueError(f"Invalid ID format: {value}. Must be a number.")

    async def on_submit(self, interaction: discord.Interaction):
        """Handle tournament creation."""
        try:
            values = [self.extract_id(input.value) for input in self.children]
            required_mentions = int(values[3])
            total_slots = int(values[4])

            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT MAX(tournament_no) FROM tournaments WHERE guild_id = ?",
                    (interaction.guild.id,)
                )
                last_tournament_no = await cursor.fetchone()
                new_tournament_no = (last_tournament_no[0] + 1) if last_tournament_no[0] else 1

                await db.execute(
                    "INSERT INTO tournaments (guild_id, tournament_no, reg_channel, confirm_channel, success_role, required_mentions, total_slots, slots_filled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (interaction.guild.id, new_tournament_no, values[0], values[1], values[2], required_mentions, total_slots, 0)
                )
                await db.commit()

            await interaction.response.send_message(f"✅ Tournament #{new_tournament_no} setup complete!", ephemeral=True)

        except ValueError as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An unexpected error occurred: {str(e)}", ephemeral=True)


class TournamentEditView(discord.ui.View):
    def __init__(self, db_path, guild_id):
        super().__init__(timeout=60)
        self.db_path = db_path
        self.guild_id = guild_id
        self.tournament_index = 0
        self.tournaments = []

    async def fetch_tournaments(self):
        """Fetch tournaments from SQLite."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM tournaments WHERE guild_id = ?", (self.guild_id,))
            self.tournaments = await cursor.fetchall()
            self.tournament_index = 0 if self.tournaments else -1

    async def update_message(self, interaction: discord.Interaction):
        """Update the message with current tournament details."""
        if self.tournament_index == -1 or not self.tournaments:
            await interaction.response.edit_message(content="No tournaments found.", embed=None, view=self)
            return

        tournament = self.tournaments[self.tournament_index]
        embed = discord.Embed(title=f"Tournament {tournament[2]}", color=discord.Color.blue())
        embed.add_field(name="Success Role", value=f"<@&{tournament[5]}>" if tournament[5] else "Not Set", inline=True)
        embed.add_field(name="Total Slots", value=tournament[7], inline=True)
        embed.add_field(name="Registration Channel", value=f"<#{tournament[3]}>", inline=True)
        embed.add_field(name="Confirm Channel", value=f"<#{tournament[4]}>", inline=False)
        embed.add_field(name="Mention Requirement", value=tournament[6], inline=False)
        embed.set_footer(text=f"Page {self.tournament_index + 1} of {len(self.tournaments)}")

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, custom_id="prev_tournament")
    async def previous_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.tournaments:
            await interaction.response.defer()
            return

        self.tournament_index = (self.tournament_index - 1) % len(self.tournaments)
        await self.update_message(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="next_tournament")
    async def next_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.tournaments:
            await interaction.response.defer()
            return

        self.tournament_index = (self.tournament_index + 1) % len(self.tournaments)
        await self.update_message(interaction)

    async def update_channel(self, interaction: discord.Interaction, channel_type: str):
        """Update registration or confirmation channel."""
        if self.tournament_index == -1:
            await interaction.response.send_message("No tournaments available to edit.", ephemeral=True)
            return

        await interaction.response.send_message(f"Please mention the new {channel_type.replace('_', ' ')}.", ephemeral=True)

        def check(m):
            return m.author == interaction.user and len(m.channel_mentions) > 0

        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=60)
            new_channel = msg.channel_mentions[0]
            tournament = self.tournaments[self.tournament_index]
            async with aiosqlite.connect(self.db_path) as db:
                column = "reg_channel" if channel_type == "reg_channel" else "confirm_channel"
                await db.execute(
                    f"UPDATE tournaments SET {column} = ? WHERE guild_id = ? AND tournament_no = ?",
                    (new_channel.id, self.guild_id, tournament[2])
                )
                await db.commit()
            await interaction.followup.send(f"{channel_type.replace('_', ' ').title()} updated to: {new_channel.mention}.", ephemeral=True)
            await self.fetch_tournaments()
            await self.update_message(interaction)
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to respond. Please try again.", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.success, label="Edit Total Slots", custom_id="edit_total_slots")
    async def edit_total_slots(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.tournament_index == -1:
            await interaction.response.send_message("No tournaments available to edit.", ephemeral=True)
            return

        await interaction.response.send_message("Please provide the new total number of slots.", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.content.isdigit()

        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=30)
            new_total_slots = int(msg.content)
            tournament = self.tournaments[self.tournament_index]
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE tournaments SET total_slots = ? WHERE guild_id = ? AND tournament_no = ?",
                    (new_total_slots, self.guild_id, tournament[2])
                )
                await db.commit()
            await interaction.followup.send(f"Total slots updated to {new_total_slots}.", ephemeral=True)
            await self.fetch_tournaments()
            await self.update_message(interaction)
        except asyncio.TimeoutError:
            await interaction.followup.send("Time out or invalid input. Please try again.", ephemeral=True)

    @discord.ui.button(label="Edit Registration Channel", style=discord.ButtonStyle.blurple, custom_id="edit_reg_channel")
    async def edit_registration_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_channel(interaction, "reg_channel")

    @discord.ui.button(label="Edit Confirm Channel", style=discord.ButtonStyle.secondary, custom_id="edit_confirm_channel")
    async def edit_confirm_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_channel(interaction, "confirm_channel")

    @discord.ui.button(label="Edit Mention Requirement", style=discord.ButtonStyle.danger, custom_id="edit_mention_requirement")
    async def edit_mention_requirement(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.tournament_index == -1:
            await interaction.response.send_message("No tournaments available to edit.", ephemeral=True)
            return

        await interaction.response.send_message("Please specify how many mentions are required for registration.", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.content.isdigit()

        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=60)
            mention_count = int(msg.content)
            if mention_count >= 0:
                tournament = self.tournaments[self.tournament_index]
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "UPDATE tournaments SET required_mentions = ? WHERE guild_id = ? AND tournament_no = ?",
                        (mention_count, self.guild_id, tournament[2])
                    )
                    await db.commit()
                await interaction.followup.send(f"Registration now requires {mention_count} mentions.", ephemeral=True)
                await self.fetch_tournaments()
                await self.update_message(interaction)
            else:
                await interaction.followup.send("Please provide a valid number (0 or greater).", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to respond. Please try again.", ephemeral=True)

    async def send_initial_message(self, interaction: discord.Interaction):
        """Send the initial message with tournament details."""
        await self.fetch_tournaments()
        await self.update_message(interaction)


class TournamentView(View):
    def __init__(self, tournaments, db_path):
        super().__init__(timeout=60)
        self.tournaments = tournaments
        self.db_path = db_path
        self.current_index = 0

    async def generate_embed(self, index):
        """Generates an embed for the tournament at the given index."""
        tournament = self.tournaments[index]
        embed = discord.Embed(
            title=f"🎮 Tournament Details (ID: `{tournament[0]}`)",
            color=discord.Color.blue()
        )
        embed.add_field(name="🏷 Tournament ID", value=f"`{tournament[0]}`", inline=False)
        embed.add_field(name="🏷 Tournament No", value=f"`{tournament[2]}`", inline=False)
        embed.add_field(name="📌 Guild ID", value=f"`{tournament[1]}`", inline=False)
        embed.add_field(name="📝 Registration Channel", value=f"<#{tournament[3]}>", inline=False)
        embed.add_field(name="✅ Confirmation Channel", value=f"<#{tournament[4]}>", inline=False)
        embed.add_field(name="🏆 Success Role", value=f"<@&{tournament[5]}>", inline=False)
        embed.add_field(name="🔢 Required Mentions", value=f"`{tournament[6]}`", inline=True)
        embed.add_field(name="🎟 Total Slots", value=f"`{tournament[7]}`", inline=True)
        embed.add_field(name="👥 Slots Filled", value=f"`{tournament[8]}`", inline=True)
        return embed

    @discord.ui.button(label="⬅ Previous", style=discord.ButtonStyle.primary, custom_id="prev_tournament")
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        """Go to the previous tournament."""
        if self.current_index > 0:
            self.current_index -= 1
            embed = await self.generate_embed(self.current_index)
            await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="➡ Next", style=discord.ButtonStyle.primary, custom_id="next_tournament")
    async def next_button(self, interaction: discord.Interaction, button: Button):
        """Go to the next tournament."""
        if self.current_index < len(self.tournaments) - 1:
            self.current_index += 1
            embed = await self.generate_embed(self.current_index)
            await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="❌ Delete Tournament", style=discord.ButtonStyle.danger, custom_id="delete_tournament")
    async def delete_button(self, interaction: discord.Interaction, button: Button):
        """Delete the current tournament after confirmation."""
        tournament = self.tournaments[self.current_index]
        confirm_view = ConfirmDeleteView(tournament[0], self.db_path)
        await interaction.response.send_message(
            "Are you sure you want to delete this tournament? This action cannot be undone.",
            view=confirm_view,
            ephemeral=True
        )


class ConfirmDeleteView(View):
    def __init__(self, tournament_id, db_path):
        super().__init__(timeout=60)
        self.tournament_id = tournament_id
        self.db_path = db_path

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger, custom_id="confirm_delete")
    async def confirm_delete(self, interaction: discord.Interaction, button: Button):
        """Confirm deletion of the tournament."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM tournaments WHERE id = ?", (self.tournament_id,))
            await db.execute("DELETE FROM teams WHERE tournament_no = (SELECT tournament_no FROM tournaments WHERE id = ?)", (self.tournament_id,))
            await db.commit()
        await interaction.response.send_message("✅ Tournament and associated teams have been deleted.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary, custom_id="cancel_delete")
    async def cancel_delete(self, interaction: discord.Interaction, button: Button):
        """Cancel deletion."""
        await interaction.response.send_message("❌ Deletion canceled.", ephemeral=True)
        self.stop()


async def setup(bot):
    await bot.add_cog(Tournament(bot))
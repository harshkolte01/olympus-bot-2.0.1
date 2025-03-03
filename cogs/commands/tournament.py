import discord
from discord.ext import commands
import motor.motor_asyncio

from discord import ui
from discord.ui import View, Modal, Button, TextInput
import asyncio


# 1290548340173443147 1334160970263564329

class Tournament(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = motor.motor_asyncio.AsyncIOMotorClient("mongodb+srv://itspm955:ashish@cluster0.lau5k.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")  # Update with your MongoDB URI
        self.db = self.client["tournament_db"]  # Database name
        self.tournaments = self.db["tournaments"]  # Collection for tournament data
        self.teams = self.db["teams"]  # Collection for teams
        self.ignorerole = self.db["ignored_roles"]

    async def get_guild_data(self, guild_id):
        data = await self.tournaments.find_one({"guild_id": guild_id})
        return data if data else None

    @commands.command(name="ignorerole")
    @commands.has_permissions(administrator=True)
    async def ignorerole(self, ctx, role: discord.Role):
        """
        Command to ignore a role by adding it to the database.
        Usage: !ignorerole @role
        """
        guild_id = ctx.guild.id
        role_id = role.id

        # Check if the role is already ignored
        existing_role = await self.ignorerole.find_one({"guild_id": guild_id, "role_id": role_id})
        if existing_role:
            await ctx.send(f"Role `{role.name}` is already being ignored.")
            return

        # Add the role to the database
        await self.ignorerole.insert_one({
            "guild_id": guild_id,
            "role_id": role_id,
            "role_name": role.name  # Store the role name for reference
        })

        await ctx.send(f"Role `{role.name}` has been added to the ignored roles list.")

    @commands.command(name="delete_cr")
    @commands.has_permissions(manage_channels=True, manage_roles=True)
    async def delete_cr(self, ctx, category_name_or_id: str):
        """Deletes all channels under a category and removes matching roles"""
        guild = ctx.guild
        category = None

        # Try finding category by ID
        if category_name_or_id.isdigit():
            category = discord.utils.get(guild.categories, id=int(category_name_or_id))
        else:
            # Try finding category by name
            category = discord.utils.get(guild.categories, name=category_name_or_id)

        if not category:
            return await ctx.send("❌ Category not found.")
        
            # Prepare feedback embed
        embed = discord.Embed(
            title="Deleting Category and Associated Channels/Roles",
            description=f"**Category:** {category.name}\n**Channels to be deleted:** {len(category.channels)}\n**Roles to be deleted:** {len(category.channels)}",
            color=0xff0000
        )
        # Send feedback message
        await ctx.send(embed=embed)

        # Get all channels under the category
        channels_to_delete = category.channels

        # Get all roles that match channel names
        role_names_to_delete = [channel.name for channel in channels_to_delete]
        roles_to_delete = [discord.utils.get(guild.roles, name=role_name) for role_name in role_names_to_delete]

        # Delete channels
        for channel in channels_to_delete:
            await channel.delete()

        # Delete roles
        for role in roles_to_delete:
            if role:
                await role.delete()

        # Delete the category
        await category.delete()

        await ctx.send(f"✅ Successfully deleted category `{category.name}` and all associated channels/roles.")
        
        # Delete the category
        try:
            await category.delete()
            # Notify the user about the successful deletion
            await ctx.send(f"✅ Successfully deleted category `{category.name}` and all associated channels/roles.")
        except discord.Forbidden as e:
            print(f"Bot is not allowed to delete the category {category.name}: {e}")
            await ctx.send(f"❌ Bot does not have the necessary permissions to delete the category `{category.name}`.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def tournament(self, ctx):
        """Main tournament management command"""
        embed = discord.Embed(title="Tournament Manager", color=0x00ff00)
        view = MainDashboardView(self.bot, self.db)  # Pass db instance to the view
        await ctx.send(embed=embed, view=view)
        print(f"Tournament command executed in guild: {ctx.guild.name}")  # Debugging

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from bots or outside guilds
        
        if message.author.bot or not message.guild:
            return
        
        # Fetch guild-specific data
        guild_data = await self.get_guild_data(message.guild.id)
        if not guild_data:
            return

        # Ignore messages from ignored roles
        ignored_roles = await self.ignorerole.find({"guild_id": message.guild.id}).to_list(None)
        if ignored_roles:
            for role in ignored_roles:
                if role["role_id"] in [r.id for r in message.author.roles]:
                    return
                
        # Find the tournament linked to the message channel
        tournament = await self.tournaments.find_one(
            {"guild_id": message.guild.id, "reg_channel": message.channel.id}
        )

        # If no tournament is linked to this channel, ignore the message
        if not tournament:
            return

        # Extract tournament details
        tournament_no = tournament["tournament_no"]
        guild_id = message.guild.id
        captain_id = message.author.id

        # Check if the user is already registered in this tournament
        existing_team = await self.teams.find_one(
            {"guild_id": guild_id, "tournament_no": tournament_no, "captain_id": captain_id}
        )

        try:
            # Parse the message content
            content = message.content.strip().split('\n')
            if len(content) < 1:
                raise ValueError("Invalid format! Use: Team Name\n@member1 @member2")

            team_name = content[0].strip()
            mentions = message.mentions

            if existing_team:
                raise ValueError("❌ You are already registered in this tournament!")

            # Ensure the required number of mentions is met
            if len(mentions) < tournament["required_mentions"]:
                raise ValueError(f"Need at least {tournament['required_mentions']} team members mentioned!")

            # Validate team name
            if not team_name.lower().startswith("team"):
                raise ValueError("Team name must start with 'Team'!")

            # Check if the team name already exists
            existing_team_name = await self.teams.find_one(
                {"guild_id": guild_id, "tournament_no": tournament_no, "team_name": team_name}
            )
            if existing_team_name:
                raise ValueError("Team name already exists!")

            # Insert the team into the database
            await self.teams.insert_one({
                "guild_id": message.guild.id,
                "tournament_no": tournament_no,
                "team_name": team_name,
                "captain_id": message.author.id,
                "members": [m.id for m in mentions],
                "confirmed": True
            })

            # Increment the slots_filled counter for the tournament
            await self.tournaments.update_one(
                {"guild_id": guild_id, "tournament_no": tournament_no},
                {"$inc": {"slots_filled": 1}}
            )

            # Assign success role to the team members
            success_role = message.guild.get_role(tournament["success_role"])
            if success_role:
                for member in [message.author] + mentions:
                    await member.add_roles(success_role)

            # Update the confirmation channel with the list of confirmed teams
            confirm_channel = self.bot.get_channel(tournament["confirm_channel"])
            if confirm_channel:
                confirmed_teams = await self.teams.find(
                    {"guild_id": guild_id, "tournament_no": tournament_no, "confirmed": True}
                ).to_list(None)

                description = [
                    f"{idx+1}. **{team['team_name']}**\nPlayers: {', '.join(f'<@{m}>' for m in team['members'])}\nCaptain: <@{team['captain_id']}>"
                    for idx, team in enumerate(confirmed_teams)
                ]

                embed = discord.Embed(
                    title=f"Confirmed Teams - Tournament {tournament_no}",
                    description='\n\n'.join(description),
                    color=0x00ff00
                )
                await confirm_channel.send(embed=embed)

            # React to the message to indicate success
            await message.add_reaction('✅')

            # Check if all slots are filled
            tournament_data = await self.tournaments.find_one({"guild_id": guild_id, "tournament_no": tournament_no})
            if tournament_data["slots_filled"] >= tournament_data["total_slots"]:
                embed = discord.Embed(
                    title="All Slots Are Full",
                    description=f"Registration for Tournament {tournament_no} is now closed!",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
                await message.channel.set_permissions(message.guild.default_role, send_messages=False)

        except Exception as e:
            # Handle errors and notify the user
            embed = discord.Embed(
                description=f"{message.author.mention} {str(e)}",
                color=discord.Color.red()
            )
            await message.reply(embed=embed)
            await message.add_reaction('❌')


class MainDashboardView(ui.View):
    def __init__(self, bot, db):
        super().__init__(timeout=60)
        self.bot = bot
        self.db = db  # MongoDB instance

    async def get_tournament(self, guild_id):
        """Fetch tournament details from MongoDB."""
        return await self.db.tournaments.find_one({"guild_id": guild_id})

    @discord.ui.button(label="Edit Tournament", style=discord.ButtonStyle.primary, custom_id="edit_tournament")
    async def edit_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Displays tournament settings and allows editing."""
        guild_id = interaction.guild.id
        tournament = await self.get_tournament(guild_id)

        if not tournament:
            return await interaction.response.send_message("❌ No tournament found for this server!", ephemeral=True)

        # Create the view and fetch tournaments
        view = TournamentEditView(self.db, guild_id)
        await view.fetch_tournaments()  # Fetch all tournaments upfront

        if not view.tournaments:
            return await interaction.response.send_message("❌ No tournaments found for this server!", ephemeral=True)

        # Send the initial message with the first tournament
        await view.send_initial_message(interaction)

    
    @discord.ui.button(label="Show Tournament", style=discord.ButtonStyle.primary)
    async def show_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Displays tournament settings and allows editing."""
        guild_id = interaction.guild.id
        tournaments = await self.db["tournaments"].find({"guild_id": guild_id}).to_list(None)

        if not tournaments:
            return await interaction.response.send_message("❌ No tournament found for this server!", ephemeral=True)

        # Initialize the view with all tournaments for the guild
        view = TournamentView(tournaments, self.db)
        embed = await view.generate_embed(0)  # Start with the first tournament

        await interaction.response.send_message(embed=embed, view=view)

    @ui.button(label="Create Tournament", style=discord.ButtonStyle.blurple)
    async def create_tournament(self, interaction: discord.Interaction, button: ui.Button):
        """Opens a modal for tournament creation."""
        await interaction.response.send_modal(TournamentSetupModal(self.db))

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
        view = StartView(self.db)
        embed.set_footer(text="Tournament Groups & Roles Manager | Adjust wisely!")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class StartView(View):
    def __init__(self, db):
        super().__init__(timeout=60)
        self.db = db  # MongoDB instance

    @discord.ui.button(label="Start Creation", style=discord.ButtonStyle.primary)
    async def start_button(self, interaction: discord.Interaction, button: Button):
        """Opens a modal for channel & role creation setup."""
        await interaction.response.send_modal(InputModal(self.db))


class InputModal(Modal):
    def __init__(self, db):
        super().__init__(title="Channel/Role Creation Setup")
        self.db = db  # MongoDB instance

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

            # Processing message
            embed = discord.Embed(
                title="⏳ Processing Your Request",
                description=f"Creating {count} channels/roles with base name: {base_name}",
                color=discord.Color.orange()
            )
            msg = await interaction.followup.send(embed=embed)

            # Start creation process
            await self.create_channels_roles(interaction, base_name, count, msg)

        except Exception as e:
            error_embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    async def create_channels_roles(self, interaction, base_name, count, progress_message):
        """Creates roles & channels and stores them in MongoDB."""
        try:
            guild = interaction.guild
            category = await guild.create_category(f"{base_name}-category")
            created_channels = []
            created_roles = []

            for i in range(1, count + 1):
                # Create a role
                new_role = await guild.create_role(name=f"{base_name}-role-{i}")
                created_roles.append({"name": new_role.name, "id": new_role.id})

                # Create a text channel with permissions
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

                # Update progress message
                embed = discord.Embed(
                    title=f"📌 Progress: {i}/{count}",
                    description=f"Created: {base_name}-{i}",
                    color=discord.Color.blue()
                )
                await progress_message.edit(embed=embed)

            # Store in MongoDB
            await self.db.tournaments.update_one(
                {"guild_id": guild.id},
                {"$set": {
                    "channels": created_channels,
                    "roles": created_roles,
                    "category": {"name": category.name, "id": category.id}
                }},
                upsert=True
            )

            # Success message
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
    def __init__(self, db):
        super().__init__(title="Tournament Setup", timeout=60)
        self.db = db
        
        self.add_item(TextInput(label="Registration Channel ID"))
        self.add_item(TextInput(label="Confirmation Channel ID"))
        self.add_item(TextInput(label="Success Role ID"))
        self.add_item(TextInput(label="Required Mentions", default="3"))
        self.add_item(TextInput(label="Total Slots", placeholder="Enter number of slots"))

    def extract_id(self, value: str) -> int:
        """Extracts an integer ID from user input, ensuring it's valid."""
        try:
            return int(value.strip())  # Remove spaces and convert to int
        except ValueError:
            raise ValueError(f"Invalid ID format: {value}. Must be a number.")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            values = [self.extract_id(input.value) for input in self.children]
            required_mentions = int(values[3])
            total_slots = int(values[4])

            # Get the last tournament_no and increment it safely
            last_tournament = await self.db.tournaments.find_one(
                {"guild_id": interaction.guild.id}, 
                sort=[("tournament_no", -1)]  # Get the latest tournament
            )

            new_tournament_no = (last_tournament["tournament_no"] + 1) if last_tournament else 1

            tournament_data = {
                "tournament_no": new_tournament_no,
                "guild_id": interaction.guild.id,
                "reg_channel": values[0],
                "confirm_channel": values[1],
                "success_role": values[2],
                "required_mentions": required_mentions,
                "total_slots": total_slots,
                "slots_filled": 0  # Initialize slots_filled
            }

            # Insert new tournament correctly
            await self.db.tournaments.insert_one(tournament_data)

            await interaction.response.send_message(f"✅ Tournament #{new_tournament_no} setup complete!", ephemeral=True)

        except ValueError as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An unexpected error occurred: {str(e)}", ephemeral=True)

    def extract_id(self, input_str):
        if input_str.startswith('<#') and input_str.endswith('>'):
            return int(input_str[2:-1])
        elif input_str.startswith('<@&') and input_str.endswith('>'):
            return int(input_str[3:-1])
        else:
            return int(input_str)

class TournamentEditView(discord.ui.View):
    def __init__(self, db, guild_id):  # Fixed method name from 'init' to '__init__'
        super().__init__(timeout=60)
        self.db = db
        self.guild_id = guild_id
        self.tournament_index = 0
        self.tournaments = []

    async def fetch_tournaments(self):
        """Fetch tournaments from the database and store them in a list."""
        self.tournaments = await self.db.tournaments.find({"guild_id": self.guild_id}).to_list(length=100)
        if not self.tournaments:
            self.tournament_index = -1  # No tournaments found
        else:
            self.tournament_index = 0  # Start from the first tournament

    async def update_message(self, interaction: discord.Interaction):
        """Update the message content to reflect the current tournament details."""
        if self.tournament_index == -1 or not self.tournaments:
            await interaction.response.edit_message(content="No tournaments found.", embed=None, view=self)
            return

        tournament = self.tournaments[self.tournament_index]
        embed = discord.Embed(title=f"Tournament {tournament['tournament_no']}", color=discord.Color.blue())
        embed.add_field(name="Success Role", value=tournament.get("success_role", "Not Set"), inline=True)
        embed.add_field(name="Total Slots", value=tournament.get("total_slots", "Not Set"), inline=True)
        embed.add_field(name="Registration Channel", value=f"<#{tournament.get('reg_channel', 'Not Set')}>", inline=True)
        embed.add_field(name="Confirm Channel", value=f"<#{tournament.get('confirm_channel', 'Not Set')}>", inline=False)
        embed.add_field(name="Mention Requirement", value=tournament.get("required_mentions", "Not Set"), inline=False)
        embed.set_footer(text=f"Page {self.tournament_index + 1} of {len(self.tournaments)}")

        # Edit the original message if it exists, otherwise send a new one
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, custom_id="prev_tournament")
    async def previous_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.tournaments:
            await interaction.response.defer()
            return

        if self.tournament_index > 0:
            self.tournament_index -= 1
        else:
            self.tournament_index = len(self.tournaments) - 1  # Loop to the last tournament

        await self.update_message(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="next_tournament")
    async def next_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.tournaments:
            await interaction.response.defer()
            return

        if self.tournament_index < len(self.tournaments) - 1:
            self.tournament_index += 1
        else:
            self.tournament_index = 0  # Loop back to the first tournament

        await self.update_message(interaction)

    async def update_channel(self, interaction: discord.Interaction, channel_type: str):
        """Update channels like registration or confirmation channel."""
        if self.tournament_index == -1:
            await interaction.response.send_message("No tournaments available to edit.", ephemeral=True)
            return

        await interaction.response.send_message(f"Please mention the new {channel_type.replace('_', ' ')}.", ephemeral=True)

        def check(m):
            return m.author == interaction.user and len(m.channel_mentions) > 0

        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=60)
            new_channel = msg.channel_mentions[0]

            if new_channel:
                tournament = self.tournaments[self.tournament_index]
                await self.db.tournaments.update_one(
                    {"guild_id": self.guild_id, "tournament_no": tournament["tournament_no"]},
                    {"$set": {channel_type: new_channel.id}}
                )
                await interaction.followup.send(f"{channel_type.replace('_', ' ').title()} updated to: {new_channel.mention}.", ephemeral=True)
                await self.fetch_tournaments()  # Refresh the tournament list
                await self.update_message(interaction)
            else:
                await interaction.followup.send("No valid channel mentioned. Please try again.", ephemeral=True)
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
            await self.db.tournaments.update_one(
                {"guild_id": self.guild_id, "tournament_no": tournament["tournament_no"]},
                {"$set": {"total_slots": new_total_slots}}
            )

            await interaction.followup.send(f"Total slots updated to {new_total_slots}.", ephemeral=True)
            await self.fetch_tournaments()  # Refresh the tournament list
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

            if mention_count >= 0:  # Allow 0 as a valid input if no mentions are required
                tournament = self.tournaments[self.tournament_index]
                await self.db.tournaments.update_one(
                    {"guild_id": self.guild_id, "tournament_no": tournament["tournament_no"]},
                    {"$set": {"required_mentions": mention_count}}
                )
                await interaction.followup.send(f"Registration now requires {mention_count} mentions.", ephemeral=True)
                await self.fetch_tournaments()  # Refresh the tournament list
                await self.update_message(interaction)
            else:
                await interaction.followup.send("Please provide a valid number (0 or greater).", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to respond. Please try again.", ephemeral=True)

    async def send_initial_message(self, interaction: discord.Interaction):
        """Send the initial message with tournament details and pagination."""
        await self.fetch_tournaments()
        await self.update_message(interaction)

class TournamentView(View):
    def __init__(self, tournaments, db):
        super().__init__(timeout=60)
        self.tournaments = tournaments
        self.db = db
        self.current_index = 0

    async def generate_embed(self, index):
        """Generates an embed for the tournament at the given index."""
        tournament = self.tournaments[index]
        tournament_id = str(tournament["_id"])  # Convert ObjectId to string
        tournament_n0 = tournament["tournament_no"]
        
        embed = discord.Embed(
            title=f"🎮 Tournament Details (ID: `{tournament_id}`)",
            color=discord.Color.blue()
        )
        embed.add_field(name="🏷 Tournament ID", value=f"`{tournament_id}`", inline=False)
        embed.add_field(name="🏷 Tournament No", value=f"`{tournament_n0}`", inline=False)
        embed.add_field(name="📌 Guild ID", value=f"`{tournament['guild_id']}`", inline=False)
        embed.add_field(name="📝 Registration Channel", value=f"<#{tournament['reg_channel']}>", inline=False)
        embed.add_field(name="✅ Confirmation Channel", value=f"<#{tournament['confirm_channel']}>", inline=False)
        embed.add_field(name="🏆 Success Role", value=f"<@&{tournament['success_role']}>", inline=False)
        embed.add_field(name="🔢 Required Mentions", value=f"`{tournament['required_mentions']}`", inline=True)
        embed.add_field(name="🎟 Total Slots", value=f"`{tournament['total_slots']}`", inline=True)
        embed.add_field(name="👥 Slots Filled", value=f"`{tournament['slots_filled']}`", inline=True)

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
        tournament_id = tournament["_id"]

        # Ask for confirmation
        confirm_view = ConfirmDeleteView(tournament_id, self.db)
        await interaction.response.send_message(
            "Are you sure you want to delete this tournament? This action cannot be undone.",
            view=confirm_view,
            ephemeral=True
        )


class ConfirmDeleteView(View):
    def __init__(self, tournament_id, db):
        super().__init__(timeout=60)
        self.tournament_id = tournament_id
        self.db = db

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger, custom_id="confirm_delete")
    async def confirm_delete(self, interaction: discord.Interaction, button: Button):
        """Confirm deletion of the tournament."""
        # Delete the tournament from MongoDB
        result = await self.db["tournaments"].delete_one({"_id": self.tournament_id})
        if result.deleted_count == 1:
            # Also delete associated teams
            await self.db["teams"].delete_many({"tournament_id": str(self.tournament_id)})
            await interaction.response.send_message("✅ Tournament and associated teams have been deleted.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to delete the tournament.", ephemeral=True)

        # Disable buttons after confirmation
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary, custom_id="cancel_delete")
    async def cancel_delete(self, interaction: discord.Interaction, button: Button):
        """Cancel deletion."""
        await interaction.response.send_message("❌ Deletion canceled.", ephemeral=True)
        self.stop()

async def setup(bot):
    await bot.add_cog(Tournament(bot))



import discord
from discord.ext import commands


class _music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Music commands"""

    def help_custom(self):
              emoji = '<:music:1345800159573053440>'
              label = "Music Commands"
              description = ""
              return emoji, label, description

    @commands.group()
    async def __Music__(self, ctx: commands.Context):
        """`play` , `join` , `disconnect`, `247` ,"""
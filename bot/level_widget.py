import discord
from discord.ext import commands

class LevelWidget(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("LevelWidget initialized")

async def setup(bot):
    print("Setting up LevelWidget")
    await bot.add_cog(LevelWidget(bot))
    print("LevelWidget added to bot")

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path='settings/.env')
TOKEN = os.getenv('TOKEN')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await bot.load_extension('bot.activity_tracker')
    await bot.load_extension('bot.commands')
    await bot.load_extension('bot.games')
    await bot.load_extension('bot.shop')

bot.run(TOKEN)

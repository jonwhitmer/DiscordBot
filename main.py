import discord
from discord.ext import commands
import os
import subprocess
import sys
import signal
from settings.settings import load_settings
from dotenv import load_dotenv

load_dotenv(dotenv_path='settings/.env')
TOKEN = os.getenv('TOKEN')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

def update_status_offline():
    script_path = os.path.join('bot', 'status', 'offline.py')
    process = subprocess.run([sys.executable, script_path], capture_output=True, text=True)

    if process.returncode == 0:
        print("Bot status updated to OFFLINE.")
    else:
        print(f"Failed to update bot status. Error: {process.stderr}")

def signal_handler(signal, frame):
    print("Signal received, updating status to OFFLINE...")
    update_status_offline()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await bot.load_extension('bot.activity_tracker')
    await bot.load_extension('bot.commands')
    await bot.load_extension('bot.games.game_manager')
    await bot.load_extension('bot.misc.referral')
    await bot.load_extension('bot.shop.shop')
    print("Extensions loaded")

    # Update the bot status to ONLINE
    script_path = os.path.join('bot', 'status', 'online.py')
    process = subprocess.run([sys.executable, script_path], capture_output=True, text=True)

    if process.returncode == 0:
        print("Bot status updated to ONLINE.")
    else:
        print(f"Failed to update bot status. Error: {process.stderr}")

bot.run(TOKEN)

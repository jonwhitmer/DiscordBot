# commands.py
from discord.ext import commands
import discord
from utils.graphics import generate_level_image, generate_statistics_visualization
import pandas as pd
from datetime import datetime, timedelta
import random
import pytz
from settings.settings import load_settings
import subprocess
import sys
import os
import asyncio
from discord.ui import View
from bot.activity_tracker import get_current_level, points_for_next_level
import yt_dlp as youtube_dl
from pydub import AudioSegment
from dotenv import load_dotenv
from tabulate import tabulate
import matplotlib.pyplot as plt

# Load the .env file
load_dotenv()

# Set the path to ffmpeg from .env file
ffmpeg_path = os.getenv('FFMPEG_PATH')
os.environ["PATH"] += os.pathsep + ffmpeg_path
AudioSegment.converter = os.path.join(ffmpeg_path, 'ffmpeg.exe')
AudioSegment.ffmpeg = os.path.join(ffmpeg_path, 'ffmpeg.exe')
AudioSegment.ffprobe = os.path.join(ffmpeg_path, 'ffprobe.exe')

TESTING = False
settings = load_settings()
coin_icon = settings['coin_icon']

class GeneralCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='gift')
    async def gift(self, ctx, recipient: discord.Member, amount: int, *, reason: str):
        if amount <= 0:
            await ctx.send("Gift amount must be positive.")
            return

        if ctx.author == recipient:
            await ctx.send(f"You cannot gift {coin_icon} to yourself.")
            return

        activity_tracker = self.bot.get_cog('ActivityTracker')
        success, message = activity_tracker.transfer_coins(ctx.author, recipient, amount)
        
        if success:
            await ctx.send(f"{ctx.author.mention} gifted {amount} {coin_icon} to {recipient.mention} for: {reason}")
        else:
            await ctx.send(f"Failed to gift {coin_icon}: {message}")

    @commands.command(name='forbeslist')
    async def forbeslist(self, ctx):
        activity_tracker = self.bot.get_cog('ActivityTracker')
        all_data = activity_tracker.activity_data

        # Convert data to a list of tuples and sort by coins
        coin_list = [(user_id, data['coins']) for user_id, data in all_data.items() if 'coins' in data]
        sorted_coin_list = sorted(coin_list, key=lambda x: x[1], reverse=True)[:10]

        # Create DataFrame
        data = {
            "Rank": list(range(1, len(sorted_coin_list) + 1)),
            "Player Name": [self.bot.get_user(int(user_id)).display_name if self.bot.get_user(int(user_id)) else "Unknown User" for user_id, _ in sorted_coin_list],
            f"Coins": [coins for _, coins in sorted_coin_list]
        }
        df = pd.DataFrame(data)

        # Plot the table with a cleaner style
        fig, ax = plt.subplots(figsize=(5, 2))  # Adjusted figsize for better appearance
        ax.axis('tight')
        ax.axis('off')

        # Create table
        table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center', edges='horizontal')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.2)  # Scale up the table for better readability

        # Customize header row
        for key, cell in table.get_celld().items():
            cell.set_edgecolor('black')
            cell.set_linewidth(1)
            if key[0] == 0:
                cell.set_text_props(weight='bold', color='black') # This should work for the background color

        # Save the table as an image
        image_path = 'utils/images/forbes_list.png'
        plt.savefig(image_path, bbox_inches='tight', dpi=300)

        # Send the image in Discord
        file = discord.File(image_path, filename='forbes_list.png')
        embed = discord.Embed(title="Forbes List")
        embed.set_image(url="attachment://forbes_list.png")
        await ctx.send(embed=embed, file=file)

        # Clean up the saved image file
        os.remove(image_path)

    @commands.command(name='update_notes')
    async def update_notes(self, ctx, *, notes):
        try:
            # Determine if the bot is online or offline
            online_status = True  # Replace with your logic to determine the status

            script_path = os.path.join('bot', 'status', 'online.py' if online_status else 'offline.py')

            # Run the update_additional_notes method in the respective script
            process = subprocess.run([sys.executable, script_path, notes], capture_output=True, text=True)

            if process.returncode == 0:
                print("Successful Notes Change")
            else:
                await ctx.send(f"Failed to update additional notes. Error: {process.stderr}")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command(name='daily')
    async def daily(self, ctx):
        user_id = str(ctx.author.id)
        activity_tracker = self.bot.get_cog('ActivityTracker')
        user_data = activity_tracker.activity_data.get(user_id, {})

        if ctx.message.content.strip() != '!daily':
            return

        if TESTING:
            last_daily = None
        else:
            last_daily = user_data.get('last_daily', None)

        now = datetime.utcnow()

        if last_daily:
            last_daily_time = datetime.strptime(last_daily, "%Y-%m-%d %H:%M:%S")
            if now < last_daily_time + timedelta(hours = 24):
                next_claim_time = last_daily_time + timedelta(hours = 24)
                est = pytz.timezone('US/Eastern')
                next_claim_time_est = next_claim_time.replace(tzinfo=pytz.utc).astimezone(est)
                next_claim_time_str = next_claim_time_est.strftime('%Y-%m-%d %I:%M:%S %p')
                await ctx.send(f"You have already claimed your daily {coin_icon}.  NEXT CLAIM TIME: {next_claim_time_str} EST.")
                return
            
        daily_coins = random.randint(0, 10000)
        digits = str(daily_coins)

        await ctx.send(f"{ctx.author.mention}, generating your daily coins...")
        
        accumulated_digits = ""
        for digit in digits:
            accumulated_digits += digit
            await ctx.send(f"{accumulated_digits}")
            await asyncio.sleep(0.5)

        activity_tracker.update_user_coins(ctx.author, daily_coins)
        activity_tracker.activity_data[user_id]['last_daily'] = now.strftime('%Y-%m-%d %H:%M:%S')
        activity_tracker.save_activity_data()

        await ctx.send(f"You have been rewarded {daily_coins} {coin_icon} for the day!  Your balance is now {activity_tracker.activity_data[user_id]['coins']} {coin_icon}.")

    @commands.command(name='coinbalance')
    async def coinbalance(self, ctx, mentioned_user: discord.Member = None):
        if mentioned_user:
            user_id = str(mentioned_user.id)
            user_name = mentioned_user.display_name
        else:
            mentioned_user = ctx.author
            user_id = str(ctx.author.id)
            user_name = ctx.author.display_name

        activity_tracker = self.bot.get_cog('ActivityTracker')
        user_data = activity_tracker.activity_data.get(user_id, {})
        coins = user_data.get('coins', 0)
        coin_icon = load_settings()['coin_icon']

        if mentioned_user == ctx.author:
            await ctx.send(f"{ctx.author.mention}, you have {coins} {coin_icon} in your account.")
        else:
            await ctx.send(f"{ctx.author.mention}, {user_name} has {coins} {coin_icon} in their account.")

class LevelUIView(View):
    def __init__(self, username, avatar_url, points, current_level, next_level, progress_percentage, remaining_points):
        super().__init__(timeout=60)
        self.username = username
        self.avatar_url = avatar_url
        self.points = points
        self.current_level = current_level
        self.next_level = next_level
        self.progress_percentage = progress_percentage
        self.remaining_points = remaining_points

class LevelUI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='level')
    async def level(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author

        activity_tracker = self.bot.get_cog('ActivityTracker')
        user_stats = activity_tracker.get_statistics(str(member.id))
        if not user_stats:
            await ctx.send("No statistics available for this user.")
            return

        username = member.display_name
        avatar_url = member.avatar.url
        points = user_stats.get("points", 0)
        current_level, remaining_points = get_current_level(points)
        next_level = current_level + 1
        progress_percentage = (points - points_for_next_level(current_level - 1)) / remaining_points * 100

        image_buffer = generate_level_image(username, current_level, progress_percentage, points, next_level, avatar_url)
    
        if image_buffer:
            file = discord.File(image_buffer, filename="level_image.png")
            embed = discord.Embed(title="Level Information", color=discord.Color.orange())
            embed.set_image(url="attachment://level_image.png")

            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send("An error occurred while generating the level image.")

    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx):
        activity_tracker = self.bot.get_cog('ActivityTracker')
        stats = {user_id: data for user_id, data in activity_tracker.activity_data.items()}
        sorted_stats = sorted(stats.items(), key=lambda x: x[1]['points'], reverse=True)[:20]
        
        df = pd.DataFrame(columns=["Rank", "Username", "Level", "Points"])
        for idx, (user_id, data) in enumerate(sorted_stats, start=1):
            member = ctx.guild.get_member(int(user_id))
            if member:
                df = pd.concat([df, pd.DataFrame({"Rank": [idx], "Username": [member.display_name], "Level": [data['level']], "Points": [data['points']]})], ignore_index=True)
        
        table_str = df.to_markdown(index=False)
        embed = discord.Embed(title="Leaderboard", color=discord.Color.green())
        embed.add_field(name="Top 20 Users", value=f"```\n{table_str}\n```", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name='leaderboard_today')
    async def leaderboard_today(self, ctx):
        activity_tracker = self.bot.get_cog('ActivityTracker')
        stats = {user_id: data for user_id, data in activity_tracker.activity_data.items()}
        sorted_stats = sorted(stats.items(), key=lambda x: x[1].get('points_today', 0), reverse=True)[:20]

        df = pd.DataFrame(columns=["Rank", "Username", "Points Today"])
        for idx, (user_id, data) in enumerate(sorted_stats, start=1):
            member = ctx.guild.get_member(int(user_id))
            if member:
                df = pd.concat([df, pd.DataFrame({"Rank": [idx], "Username": [member.display_name], "Points Today": [data.get('points_today', 0)]})], ignore_index=True)

        table_str = df.to_markdown(index=False)
        embed = discord.Embed(title="Today's Leaderboard", color=discord.Color.green())
        embed.add_field(name="Top 20 Users", value=f"```\n{table_str}\n```", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name='statistics')
    async def statistics(self, ctx, *, member: discord.Member = None):
        if member is None:
            member = ctx.author
        stats = self.bot.get_cog('ActivityTracker').get_statistics(str(member.id))
        if stats:
            embed = discord.Embed(title="Statistics", color=discord.Color.purple())
            embed.add_field(name="Username", value=member.display_name, inline=True)
            embed.add_field(name="Total Points", value=stats.get('points', 0), inline=True)
            embed.add_field(name="Level", value=stats.get('level', 1), inline=True)
            embed.add_field(name="XP to Next Level", value=stats.get('xp_to_next_level', 0), inline=True)
            embed.add_field(name="Minutes in Voice", value=stats.get('minutes_in_voice', 0), inline=True)
            embed.add_field(name="Minutes Online", value=stats.get('minutes_online', 0), inline=True)
            embed.add_field(name="Messages Sent", value=stats.get('messages_sent', 0), inline=True)
            embed.add_field(name="Characters Typed", value=stats.get('characters_typed', 0), inline=True)
            embed.add_field(name="Points Today", value=stats.get('points_today', 0), inline=True)

            # Add coin information
            coins = stats.get('coins', 0)
            coin_icon_url = "https://cdn4.iconfinder.com/data/icons/coins-virtual-currency/104/Guarani-256.png"
            embed.add_field(name=f"\u200b", value=f"[![coins]({coin_icon_url})]({coin_icon_url}) **{coins}**", inline=False)

            await ctx.send(embed=embed)
        else:
            await ctx.send("No statistics available for this user.")

    @commands.command(name='statistics_visualization')
    async def statistics_visualization(self, ctx, *, member: discord.Member = None):
        if member is None:
            member = ctx.author
        stats = self.bot.get_cog('ActivityTracker').get_statistics(str(member.id))
        if stats:
            # Generate the visualization
            visualization_path = generate_statistics_visualization(stats)
            embed = discord.Embed(title="Statistics Visualization", color=discord.Color.purple())
            file = discord.File(visualization_path, filename="statistics_visualization.png")
            embed.set_image(url=f"attachment://statistics_visualization.png")
            await member.send(embed=embed, file=file)
        else:
            await ctx.send("No statistics available for this user.")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            botlog_channel = discord.utils.get(ctx.guild.channels, name='botlog')
            if botlog_channel:
                await botlog_channel.send("Invalid Command Called.")
        else:
            raise error
        
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_player = None
        self.voice_channel = None
        self.votes_to_skip = set()
        self.song_queue = asyncio.Queue()
        self.playing_song = None
        self.current_volume = 0.2

    @commands.command(name='play')
    async def play(self, ctx, url):
        user = ctx.author
        activity_tracker = self.bot.get_cog('ActivityTracker')
        user_data = activity_tracker.get_statistics(str(user.id))
        user_coins = user_data.get('coins', 0)
        settings = load_settings()
        coin_icon = settings['coin_icon']

        try:
            video_info = await self.get_video_info(url)
            video_length = video_info['duration']  # Duration in seconds
            video_title = video_info['title']
            cost = video_length * 4

            if user_coins < cost:
                await ctx.send(f"{user.mention}, the cost is {cost} {coin_icon}, but you do not have enough {coin_icon}.")
                return

            await ctx.send(f"{user.mention}, the cost to play '{video_title}' is {cost} {coin_icon}. Type `!accept` to proceed.")
            
            def check(m):
                return m.author == user and m.content.lower() == '!accept'
            
            try:
                await self.bot.wait_for('message', check=check, timeout=30.0)
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond!")
                return

            activity_tracker.update_user_activity(user, coins=-cost)
            await ctx.send(f"{user.mention} has paid {cost} {coin_icon} to play '{video_title}'.")

            self.voice_channel = ctx.author.voice.channel
            if not self.voice_channel:
                await ctx.send("You are not connected to a voice channel.")
                return

            audio_file = await self.download_audio(url, video_title)
            await self.song_queue.put((ctx, audio_file, video_title, user))
            if not self.current_player:
                await self.play_next_song()

        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    async def play_next_song(self):
        if not self.song_queue.empty():
            ctx, audio_file, video_title, user = await self.song_queue.get()
            self.voice_channel = ctx.author.voice.channel
            voice = await self.voice_channel.connect()

            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(audio_file), volume=self.current_volume)
            self.current_player = voice.play(source, after=lambda e: self.bot.loop.create_task(self.play_next_song()))

            self.playing_song = (ctx, video_title, user)
            await ctx.send(f"Now playing: '{video_title}'")

            while voice.is_playing():
                await asyncio.sleep(1)
            await voice.disconnect()
            os.remove(audio_file)
            await ctx.send(f"Finished playing: '{video_title}' and removed the file from the system.")
            self.playing_song = None
            self.current_player = None

    @commands.command(name='skip')
    async def skip(self, ctx):
        if not self.current_player:
            await ctx.send("No audio is currently playing.")
            return

        user = ctx.author
        if user == self.playing_song[2]:  # The user who requested the song
            self.current_player.source.cleanup()
            self.current_player.stop()
            await ctx.send(f"{user.mention} has skipped their own song.")
            self.votes_to_skip.clear()
        else:
            if user not in self.voice_channel.members:
                await ctx.send("You must be in the voice channel to vote to skip.")
                return

            self.votes_to_skip.add(user)
            total_members = len(self.voice_channel.members)
            if len(self.votes_to_skip) / total_members >= 0.5:
                self.current_player.source.cleanup()
                self.current_player.stop()
                await ctx.send("Vote passed! Skipping the current song.")
                self.votes_to_skip.clear()
            else:
                await ctx.send(f"{user.mention} has voted to skip. {len(self.votes_to_skip)}/{total_members} votes.")

    @commands.command(name='volume')
    async def volume(self, ctx, volume: float):
        user = ctx.author
        if user != self.playing_song[2]:
            await ctx.send(f"{user.mention}, only the song requester can change the volume.")
            return

        if volume < 0 or volume > 5:
            await ctx.send(f"{user.mention}, volume must be between 0 and 5.")
            return

        self.current_volume = volume * 0.1
        if self.current_player and self.current_player.source:
            self.current_player.source.volume = self.current_volume
        await ctx.send(f"{user.mention}, the volume has been set to {volume}.")

    async def get_video_info(self, url):
        ydl_opts = {
            'format': 'bestaudio/best',
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            'duration': info['duration'],
            'title': info['title']
        }

    async def download_audio(self, url, title):
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'utils/sounds/musicdump/{title}.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffmpeg_location': os.getenv('FFMPEG_PATH'),
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url)
            filename = ydl.prepare_filename(info)
            mp3_filename = filename.replace('.webm', '.mp3')
        
        return mp3_filename

async def setup(bot):
    await bot.add_cog(GeneralCommands(bot))
    await bot.add_cog(LevelUI(bot))
    await bot.add_cog(Music(bot))


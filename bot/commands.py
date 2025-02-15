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
from gtts import gTTS
from pydub import AudioSegment

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
        ActivityTracker = self.bot.get_cog('ActivityTracker')

        if amount <= 0:
            await ctx.send("Gift amount must be positive.")
            return

        if ctx.author == recipient:
            await ctx.send(f"You cannot gift {coin_icon} to yourself.")
            return

        success, message = ActivityTracker.transfer_coins(ctx.author, recipient, amount)
        
        if success:
            await ctx.send(f"{ctx.author.mention} gifted {amount} {coin_icon} to {recipient.mention} for: {reason}")
        else:
            await ctx.send(f"Failed to gift {coin_icon}: {message}")

    @commands.command(name='forbeslist')
    async def forbeslist(self, ctx):
        ActivityTracker = self.bot.get_cog('ActivityTracker')
        top_users = ActivityTracker.get_top_users_by_coins()

        # Create DataFrame
        data = {
            "Rank": list(range(1, len(top_users) + 1)),
            "Player Name": [self.bot.get_user(int(user_id)).display_name if self.bot.get_user(int(user_id)) else username for user_id, username, _ in top_users],
            "Coins": [f"{coins:,}" for _, _, coins in top_users]  # This formats the coins with commas
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

    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx):
        ActivityTracker = self.bot.get_cog('ActivityTracker')
        top_users = ActivityTracker.get_points_leaderboard()

        # Create DataFrame
        data = {
            "Rank": list(range(1, len(top_users) + 1)),
            "Player Name": [
                self.bot.get_user(int(user_id)).display_name if self.bot.get_user(int(user_id)) else username 
                for user_id, username, level, points, coins in top_users
            ],
            "Level": [level for _, _, level, _, _ in top_users],
            "Points": [f"{points:,}" for _, _, _, points, _ in top_users],
            "Coins": [f"{coins:,}" for _, _, _, _, coins in top_users]  # This formats the coins with commas
        }
        df = pd.DataFrame(data)

        # Plot the table with a cleaner style
        fig, ax = plt.subplots(figsize=(6, 5))  # Adjusted figsize for better appearance
        ax.axis('tight')
        ax.axis('off')

        # Create table
        table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center', edges='horizontal')
        table.auto_set_font_size(False)
        table.set_fontsize(15)
        table.scale(1.5, 2.0)  # Scale up the table for better readability

        # Customize header row
        for key, cell in table.get_celld().items():
            cell.set_edgecolor('black')
            cell.set_linewidth(1.5)
            if key[0] == 0:
                cell.set_text_props(weight='bold', color='black')  # Bold headers

        # Save the table as an image
        image_path = 'utils/images/leaderboard.png'
        plt.savefig(image_path, bbox_inches='tight', dpi=300)

        # Send the image in Discord
        file = discord.File(image_path, filename='leaderboard.png')
        embed = discord.Embed(title="Leaderboard")
        embed.set_image(url="attachment://leaderboard.png")
        await ctx.send(embed=embed, file=file)

        # Clean up the saved image file
        os.remove(image_path)

    @commands.command(name='daily')
    async def daily(self, ctx):
        if ctx.channel.id != 1252055670778368013 and ctx.channel.id != 1259664562924552213:
            await ctx.send("Please utilize the <#1252055670778368013> channel to use the `!daily` command.")
            return
    
        user_id = str(ctx.author.id)
        ActivityTracker = self.bot.get_cog('ActivityTracker')

        last_daily = ActivityTracker.fetch_query('SELECT "Last Daily" FROM user_stats WHERE ID = ?', (user_id,))
        last_daily = last_daily[0][0]

        if not last_daily:
            await ctx.send("User data not found.")
            return

        if ctx.message.content.strip() != '!daily':
            return

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

        coin_balance = ActivityTracker.fetch_query('SELECT Coins FROM user_info WHERE ID = ?', (user_id,))
        coin_balance = coin_balance[0][0]

        new_balance = coin_balance + daily_coins

        ActivityTracker.execute_query('UPDATE user_info SET Coins = ? WHERE ID = ?', (new_balance, user_id))
        ActivityTracker.execute_query('UPDATE user_stats SET "Last Daily" = ? WHERE ID = ?', (now.strftime('%Y-%m-%d %H:%M:%S'), user_id))

        await ctx.send(f"You have been rewarded {daily_coins} {coin_icon} for the day!  Your balance is now {new_balance} {coin_icon}.")
        
    @commands.command(name='loandisbursement')
    async def loandisbursement(self, ctx):
        if ctx.channel.id != 1252055670778368013 and ctx.channel.id != 1259664562924552213:
            await ctx.send("Please utilize the <#1252055670778368013> channel to use the `!loandisbursement` command.")
            return

        user_id = str(ctx.author.id)
        ActivityTracker = self.bot.get_cog('ActivityTracker')

        last_loan_disbursement = ActivityTracker.fetch_query('SELECT "Last Loan Disbursement" FROM user_stats WHERE ID = ?', (user_id,))

        if last_loan_disbursement and last_loan_disbursement[0][0]:
            last_loan_disbursement = last_loan_disbursement[0][0]
        else:
            last_loan_disbursement = None

        if ctx.message.content.strip() != '!loandisbursement':
            return

        now = datetime.utcnow()

        if last_loan_disbursement:
            last_loan_time = datetime.strptime(last_loan_disbursement, "%Y-%m-%d %H:%M:%S")
            if now < last_loan_time + timedelta(hours=24):
                next_claim_time = last_loan_time + timedelta(hours=24)
                est = pytz.timezone('US/Eastern')
                next_claim_time_est = next_claim_time.replace(tzinfo=pytz.utc).astimezone(est)
                next_claim_time_str = next_claim_time_est.strftime('%Y-%m-%d %I:%M:%S %p')
                await ctx.send(f"You have already signaled a loan disbursement today. NEXT SIGNAL TIME: {next_claim_time_str} EST.")
                return

        members = ctx.guild.members
        eligible_members = [member for member in members if not member.bot and member.id != ctx.author.id]

        if not eligible_members:
            await ctx.send("No eligible members found for loan disbursement.")
            return

        random_member = random.choice(eligible_members)
        random_member_id = str(random_member.id)
        loan_amount = random.randint(0, 10000)
        digits = str(loan_amount)

        await ctx.send(f"{ctx.author.mention} has signaled a loan disbursement!")
        await ctx.send(f"A lucky member will be getting a loan disbursement!")

        accumulated_digits = ""
        for digit in digits:
            accumulated_digits += digit
            await ctx.send(f"{accumulated_digits}")
            await asyncio.sleep(0.5)
        
        random_member_balance = ActivityTracker.fetch_query('SELECT Coins FROM user_info WHERE ID = ?', (random_member_id,))

        if random_member_balance:
            random_member_balance = random_member_balance[0][0]
        else:
            random_member_balance = 0

        new_balance = random_member_balance + loan_amount

        ActivityTracker.execute_query('UPDATE user_info SET Coins = ? WHERE ID = ?', (new_balance, random_member_id))
        ActivityTracker.execute_query('UPDATE user_stats SET "Last Loan Disbursement" = ? WHERE ID = ?', (now.strftime('%Y-%m-%d %H:%M:%S'), user_id))

        await ctx.send(f"{random_member.mention} has been rewarded {loan_amount} {coin_icon} for the day! Their balance is now {new_balance} {coin_icon}.")

    @commands.command(name='medicare')
    async def medicare(self, ctx):
        await ctx.send("Joe Biden has officially beat medicare!")
        await asyncio.sleep(5)
        await ctx.send("Oh wait.. ***I forgot.***")

        # Image URL
        image_url = 'https://www.indy100.com/media-library/image.png?id=33573844&width=1200&height=800&quality=85&coordinates=0%2C14%2C0%2C13'
        
        embed = discord.Embed()
        embed.set_image(url=image_url)
    
        await ctx.send(embed=embed)

    @commands.command(name='boner')
    async def boner(self, ctx):
        responses = [
            "You know you're getting old when your boner takes longer to rise than your morning coffee.",
            "Had a boner this morning...then realized I was just excited for breakfast.",
            "Why don't boners get arrested? They always get off with a stiff warning.",
            "Just saw a guy with a boner in public. I guess some people really are morning people.",
            "Got a boner today, but it was just my cat rubbing against me. Thanks, Fluffy.",
            "Why did my boner cross the road? To get away from my ex.",
            "My boner and I have an understanding: it shows up at the worst times possible.",
            "Ever had a boner so awkward it should come with an apology note?",
            "Boner in public? Just tell them it's your phone on vibrate. Works every time.",
            "My boner just texted me: 'Stop wearing tight pants!'",
            "Got a boner during a Zoom call. Thank God for the mute button.",
            "You know it's going to be a good day when your boner wakes up before you do.",
            "My boner and my alarm clock should synchronize. That way, I can hit snooze on both.",
            "Boner during a meeting? Just pretend you’re deeply pondering the budget report.",
            "If boners could talk, mine would constantly be saying, 'Not now, dude!'",
            "Boner and gym shorts: a match made in awkward heaven.",
            "Had a boner while reading...a menu. Guess I was really hungry.",
            "Boner in a tight spot? Just start a conversation about politics; it'll go away instantly.",
            "Ever had a boner so random you had to question your life choices?",
            "My boner has a better social life than I do. It's always up for something.",
            "Nothing like a boner to remind you that your body has a mind of its own.",
            "Got a boner while watching cartoons. Childhood nostalgia hit differently."
        ]
        response = random.choice(responses)
        await ctx.send(response)

    @commands.command(name='coinbalance')
    async def coinbalance(self, ctx, mentioned_user: discord.Member = None):
        if mentioned_user:
            user_id = str(mentioned_user.id)
            user_name = mentioned_user.display_name
        else:
            mentioned_user = ctx.author
            user_id = str(ctx.author.id)
            user_name = ctx.author.display_name

        ActivityTracker = self.bot.get_cog('ActivityTracker')
        coins = ActivityTracker.get_coins(user_id)

        if mentioned_user == ctx.author:
            await ctx.send(f"{ctx.author.mention}, you have {coins} {coin_icon} in your account.")
        else:
            await ctx.send(f"{ctx.author.mention}, {user_name} has {coins} {coin_icon} in their account.")

    @commands.command(name='fredtalk')
    async def fredtalk(self, ctx, *, message: str = None):
        if ctx.author.voice and ctx.author.voice.channel:
            voice_channel = ctx.author.voice.channel
            vc = await voice_channel.connect()

            user_nicknames = [member.display_name for member in voice_channel.members if member.display_name != "Fred"]

            if message:
                tts_message = message
            else:
                if len(user_nicknames) == 1:
                    tts_message = f"Hello {user_nicknames[0]}"
                else:
                    tts_message = " ".join([f"Hello {name}" for name in user_nicknames])

            tts_file_path = os.path.join('utils', 'sounds', 'bottalking', 'tts.mp3')
            tts = gTTS(tts_message, lang='en', tld='co.in')
            tts.save(tts_file_path)

            # Load the TTS file with pydub
            sound = AudioSegment.from_file(tts_file_path)

            # Deepen the pitch (lowering by 4 semitones)
            new_sound = sound._spawn(sound.raw_data, overrides={
                "frame_rate": int(sound.frame_rate * 0.6)
            }).set_frame_rate(sound.frame_rate)

            # Save the new sound
            new_tts_file_path = os.path.join('utils', 'sounds', 'bottalking', 'tts_deep.mp3')
            new_sound.export(new_tts_file_path, format="mp3")

            vc.play(discord.FFmpegPCMAudio(source=new_tts_file_path))

            while vc.is_playing():
                await asyncio.sleep(1)

            await vc.disconnect()

            # Delete the TTS files after 10 seconds
            await asyncio.sleep(5)
            if os.path.exists(tts_file_path):
                os.remove(tts_file_path)
            if os.path.exists(new_tts_file_path):
                os.remove(new_tts_file_path)
        else:
            await ctx.send("You aren't in a voice chat.")

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

        ActivityTracker = self.bot.get_cog('ActivityTracker')

        username = member.display_name
        avatar_url = member.avatar.url
        points = ActivityTracker.get_points(member.id)
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
        
        ActivityTracker = self.bot.get_cog("ActivityTracker")
        user_id = member.id

        if ActivityTracker:
            embed = discord.Embed(title="Statistics", color=discord.Color.purple())
            embed.add_field(name="Username", value=f"**{member.display_name}**", inline=True)
            embed.add_field(name="Total Points", value=ActivityTracker.get_points(user_id), inline=True)
            embed.add_field(name="Level", value=ActivityTracker.get_level(user_id), inline=True)
            embed.add_field(name="Total Minutes in Voice Chat", value=ActivityTracker.get_from_database(user_id, "Total Minutes in Voice Chat"), inline=True)
            embed.add_field(name="Total Minutes Online", value=ActivityTracker.get_from_database(user_id, "Total Minutes Online"), inline=True)
            embed.add_field(name="Total Messages Sent", value=ActivityTracker.get_from_database(user_id, "Total Messages Sent"), inline=True)
            embed.add_field(name="Total Characters Typed", value=ActivityTracker.get_from_database(user_id, "Total Characters Typed"), inline=True)

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

    @commands.command(name='flipoff')
    async def flipoff(self, ctx, *, target: discord.Member = None):
        ActivityTracker = self.bot.get_cog('ActivityTracker')

        if target is None:
            await ctx.send(f"{ctx.author.mention}, you need to specify someone to flip off! Example: `!flipoff @user`.")
            return

        if target == ctx.author:
            await ctx.send(f"{ctx.author.mention}, you cannot flip yourself off!")
            return

        await ctx.send(f"{ctx.author.mention} is flipping off {target.mention}!")

        flipoff_art = "\n".join([
            "⠀⠀⠀⢀⣠⣤⣤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⢠⣾⡿⠛⠻⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠸⣿⠧⠿⠶⠋⢻⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⢻⡄⠀⢀⣀⠈⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠈⣿⡀⠛⠉⠀⠹⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⢸⣧⠀⠀⠀⠀⢻⣦⣤⣤⣤⣤⢤⣄⡀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⢰⡿⡿⡄⢀⣠⣤⣀⢻⡁⠀⠈⢧⠀⠈⠻⣦⠀⠀⠀⠀",
            "⠀⠀⣰⣿⣛⣀⣷⠘⠫⠟⠛⠀⢣⠀⠀⠀⢣⠀⠀⠘⢷⡀⠀⠀",
            "⢀⣾⣿⠟⠃⠀⠘⣇⠀⠀⠀⠀⠈⢧⠀⠀⠀⢧⠀⠀⠈⢻⣄⠀",
            "⢸⡇⡇⠀⠀⠀⠀⠈⢆⠀⠀⠀⠀⠈⣆⠀⠀⠘⣧⠀⠀⠀⢻⡄",
            "⠈⣷⢹⡀⠀⠀⠀⠀⠘⣆⠀⠀⠀⠀⠘⡄⠀⠀⠋⠀⠀⢀⣿⠁",
            "⠀⣿⠈⢇⠀⠀⠀⠀⠐⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⢀⣾⠃⠀",
            "⠀⣿⠀⠘⡄⠀⠀⠀⠀⠈⠀⠀⠀⠀⠀⠀⢠⠀⠀⣸⡿⠃⠀⠀",
            "⠀⠙⠳⣦⣽⡄⠀⠀⠀⠀⢸⡀⠀⠀⠀⠀⣸⡶⠾⠋⠀⠀⠀⠀",
            "⠀⠀⠀⠈⠻⣿⣦⣄⣀⣤⠴⠷⢤⣤⠶⠟⠁⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠈⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
        ])

        await ctx.send(f"{flipoff_art}")
        await asyncio.sleep(2)

        # Randomization game: Coin Spinner
        await ctx.send(f"{target.mention}, a coin spinner is deciding your fate!")

        spinner_message = await ctx.send("Spinning: 🟢🔴")
        outcomes = ["🟢", "🔴", "🟢"]
        mugged = random.choice([True, False])
        spin_result = random.choice(outcomes)

        for _ in range(10):
            random_spin = random.choice(outcomes)
            await spinner_message.edit(content=f"Spinning: {random_spin}")
            await asyncio.sleep(1)

        # Final outcome
        await asyncio.sleep(1)
        await spinner_message.edit(content=f"Final Result: {spin_result}")

        if mugged and spin_result == "🔴":
            user_id = str(target.id)
            plr_id = str(ctx.author.id)
            coins = ActivityTracker.get_coins(user_id)
            loss = random.randint(1, coins)  # Limit loss to available coins or 10,000

            ActivityTracker.update_coins(user_id, -loss)
            ActivityTracker.update_coins(plr_id, loss)
            await ctx.send(f"Oh no! {target.mention}, you got mugged and lost {loss} coins! Better luck next time!")
            await asyncio.sleep(2)
            await ctx.send(f"{ctx.author.id}, you stole {loss} of {target.mention}'s coins!")
        else:
            await ctx.send(f"{target.mention}, you got lucky and escaped the mugging! 🎉")
'''    
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
'''

async def setup(bot):
    await bot.add_cog(GeneralCommands(bot))
    await bot.add_cog(LevelUI(bot))
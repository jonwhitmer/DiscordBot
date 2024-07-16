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

TESTING = False
settings = load_settings()
coin_icon = settings['coin_icon']

class GeneralCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
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

async def setup(bot):
    await bot.add_cog(GeneralCommands(bot))
    await bot.add_cog(LevelUI(bot))


# bot/commands.py
from discord.ext import commands
import discord
from utils.graphics import generate_level_image, generate_statistics_visualization
from discord.ui import View, Button
import pandas as pd
from bot.games import Duel, BlackjackGame, DUEL_WIN_POINTS, DUEL_WIN_COINS, BOT_TESTING_MODE
import asyncio
import aiohttp

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
        
        # Dummy data for illustration
        username = member.display_name
        avatar_url = member.avatar.url
        points = 20
        current_level = 1
        next_level = 2
        progress_percentage = 1.00
        remaining_points = 100  # Calculate the remaining points needed to reach the next level
        
        # Create the embed with initial information
        embed = discord.Embed(title="Level Information", color=discord.Color.orange())
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name=f"{username}", value=f"Points: {points}", inline=False)
        embed.add_field(name=f"Level {current_level}", value=f"{progress_percentage:.2f}%", inline=True)
        embed.add_field(name=f"Next Level {next_level}", value=f"{progress_percentage:.2f}%", inline=True)

        # Create the view with the button
        view = LevelUIView(username, avatar_url, points, current_level, next_level, progress_percentage, remaining_points)
        
        await ctx.send(embed=embed, view=view)

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
    await bot.add_cog(LevelUI(bot))
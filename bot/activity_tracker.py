# activity_tracker.py
import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timezone

# Variables for point increments and bot testing mode
MESSAGE_POINTS = 10
VOICE_POINTS = 5
ONLINE_POINTS = 2
CHARACTERS_TYPED_POINTS = 0.1

class ActivityTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.activity_data = self.load_activity_data()
        self.reset_daily_stats.start()
        self.track_activity.start()

    def load_activity_data(self):
        if os.path.exists('data/player_data.json'):
            with open('data/player_data.json', 'r') as f:
                return json.load(f)
        return {}

    def save_activity_data(self):
        with open('data/player_data.json', 'w') as f:
            json.dump(self.activity_data, f, indent=4)

    @tasks.loop(hours=24)
    async def reset_daily_stats(self):
        now = datetime.now(timezone.utc)
        if now.hour == 5:  # 5 AM UTC, midnight EST
            for user_id in self.activity_data:
                self.activity_data[user_id]['points_today'] = 0
            self.save_activity_data()

    @reset_daily_stats.before_loop
    async def before_reset_daily_stats(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def track_activity(self):
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.status != discord.Status.offline and not member.bot:
                    user_id = str(member.id)
                    if user_id not in self.activity_data:
                        self.activity_data[user_id] = {
                            "username": member.name,
                            "points": 0,
                            "points_today": 0,
                            "level": 1,
                            "messages_sent": 0,
                            "characters_typed": 0,
                            "minutes_in_voice": 0,
                            "minutes_online": 0,
                            "voice_activations": 0,
                            "total_talking_time": 0,
                            "coins": 0  # Add coins attribute
                        }
                    self.activity_data[user_id]['minutes_online'] += ONLINE_POINTS  # Increment by ONLINE_POINTS
                    self.save_activity_data()

    def update_user_activity(self, user, points=0, coins=0):
        user_id = str(user.id)
        if user_id not in self.activity_data:
            self.activity_data[user_id] = {
                "username": user.name,
                "points": 0,
                "points_today": 0,
                "level": 1,
                "messages_sent": 0,
                "characters_typed": 0,
                "minutes_in_voice": 0,
                "minutes_online": 0,
                "voice_activations": 0,
                "total_talking_time": 0,
                "coins": 0  # Add coins attribute
            }
        self.activity_data[user_id]['points'] += points
        self.activity_data[user_id]['points_today'] += points
        self.activity_data[user_id]['coins'] += coins
        self.save_activity_data()

    def update_user_coins(self, user, coins):
        user_id = str(user.id)
        if user_id not in self.activity_data:
            self.activity_data[user_id] = {
                "username": user.name,
                "coins": 0,
                # Add other fields as necessary
            }
        self.activity_data[user_id]['coins'] += coins
        self.save_activity_data()

    def transfer_coins(self, from_user, to_user, amount):
        from_user_id = str(from_user.id)
        to_user_id = str(to_user.id)

        if from_user_id not in self.activity_data or to_user_id not in self.activity_data:
            return False, "User data not found."

        if self.activity_data[from_user_id]['coins'] < amount:
            return False, "Insufficient balance."

        self.activity_data[from_user_id]['coins'] -= amount
        self.activity_data[to_user_id]['coins'] += amount
        self.save_activity_data()

        return True, f"Transferred {amount} coins from {from_user.name} to {to_user.name}."

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            self.update_user_activity(message.author, points=MESSAGE_POINTS)
            self.activity_data[str(message.author.id)]['messages_sent'] += 1
            self.activity_data[str(message.author.id)]['characters_typed'] += len(message.content)
            self.save_activity_data()

    def get_statistics(self, user_id):
        return self.activity_data.get(user_id, {})
    
    def get_User_balance(self, user):
        user_id = str(user.id)
        if user_id in self.activity_data:
            return self.activity_data[user_id].get('coins', 0)
        return 0
    
def points_for_level_transition(level):
    return 10000 if level == 1 else (level + 1) * 5000

def points_for_next_level(current_level):
    total_points = 0
    for level in range(1, current_level + 1):
        total_points += points_for_level_transition(level)
    return total_points

def get_current_level(points):
    level = 1
    while points >= points_for_next_level(level):
        level += 1
    return level, points_for_next_level(level) - points_for_next_level(level - 1)


async def setup(bot):
    await bot.add_cog(ActivityTracker(bot))

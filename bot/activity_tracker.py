# activity_tracker.py
import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
import random
from datetime import datetime, timezone
from gtts import gTTS
from pydub import AudioSegment
from settings.settings import load_settings

with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

settings = load_settings()
coin_icon = settings['coin_icon']

# Variables for point increments and bot testing mode
MESSAGE_POINTS = 15
ONLINE_POINTS = 2
VOICE_CHAT_POINTS = 15

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
                print(f"Reset Points Today for {user_id}")
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
                "total_talking_time": 0,
                "coins": 0  # Add coins attribute
            }
        previous_level = self.activity_data[user_id]['level']
        self.activity_data[user_id]['points'] += points
        self.activity_data[user_id]['points_today'] += points
        self.activity_data[user_id]['coins'] += coins

        # Check for level up
        new_level, _ = get_current_level(self.activity_data[user_id]['points'])
        if new_level > previous_level:
            self.activity_data[user_id]['level'] = new_level
            # Announce level up in main chat
            self.bot.loop.create_task(
                self.announce_level_up_in_main_chat(user, previous_level, new_level)
            )
            
            # If user is in a voice channel, make the bot join and announce via TTS
            if user.voice and user.voice.channel:
                self.bot.loop.create_task(self.announce_level_up_in_voice(user, previous_level, new_level))

        self.save_activity_data()

    async def announce_level_up_in_main_chat(self, user, previous_level, new_level):
        main_channel = discord.utils.get(user.guild.text_channels, name='licker-talk')
        if main_channel:
            await main_channel.send(f"{user.mention} has leveled up from Level {previous_level} to Level {new_level}. Congratulations, Gilligano!")
            await main_channel.send(f"To celebrate, here's a gift!  Generating..")

            generated_coins = random.randint(0, 50000)
            digits = str(generated_coins)
        
            accumulated_digits = ""

            for digit in digits:
                accumulated_digits += digit
                await main_channel.send(f"{accumulated_digits}")
                await asyncio.sleep(0.5)
            
            await main_channel.send(f"{digits} {coin_icon}")

            user_id = str(user.id)
            self.activity_data[user_id]['coins'] += generated_coins

    async def announce_level_up_in_voice(self, user, previous_level, new_level):
        voice_channel = user.voice.channel
        vc = await voice_channel.connect()
        tts_message = f"{user.display_name} has leveled up from level {previous_level} to level {new_level}. Congratulations, gilligano!"
        
        tts_file_path = os.path.join('utils', 'sounds', 'bottalking', 'tts.mp3')
        tts = gTTS(tts_message, lang='en', tld='co.in')
        tts.save(tts_file_path)

        sound = AudioSegment.from_file(tts_file_path)

        # Deepen the pitch (lowering by 4 semitones)
        new_sound = sound._spawn(sound.raw_data, overrides={
            "frame_rate": int(sound.frame_rate * 0.7)
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

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot:
            user_id = str(member.id)
            if before.channel is None and after.channel is not None:
                # User has joined a voice channel
                print(f"{member.name} has joined a voice channel.")
                self.activity_data[user_id]['voice_join_time'] = datetime.now().timestamp()

            elif before.channel is not None and after.channel is None:
                # User has left a voice channel
                if 'voice_join_time' in self.activity_data[user_id]:
                    time_spent = datetime.now().timestamp() - self.activity_data[user_id]['voice_join_time']
                    points_earned = int(time_spent / 60) * VOICE_CHAT_POINTS
                    print(f"{member.name} has left the voice channel. Points earned: {points_earned}.")
                    self.update_user_activity(member, points=points_earned)
                    self.activity_data[user_id]['total_talking_time'] += int(time_spent / 60)
                    del self.activity_data[user_id]['voice_join_time']

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

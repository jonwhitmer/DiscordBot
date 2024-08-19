# activity_tracker.py
import discord
from discord.ext import commands, tasks
import os
import asyncio
import random
import sqlite3
from datetime import datetime, timezone
from gtts import gTTS
from pydub import AudioSegment
from settings.settings import load_settings

DATABASE = 'data/databases/users.db'

settings = load_settings()
coin_icon = settings['coin_icon']

# Variables for point increments and bot testing mode
MESSAGE_POINTS = 15
ONLINE_POINTS = 2
VOICE_CHAT_POINTS = 15

class ActivityTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reset_daily_stats.start()
        self.track_activity.start()

    def execute_query(self, query, params=()):
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        conn.close()

    def fetch_query(self, query, params=()):
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(query, params)
        result = c.fetchall()
        conn.close()
        return result

    @tasks.loop(hours=24)
    async def reset_daily_stats(self):
        now = datetime.now(timezone.utc)
        if now.hour == 5:  # 5 AM UTC, midnight EST
            self.execute_query('UPDATE daily_stats SET "Points Today" = 0, "Messages Sent Today" = 0, "Characters Typed Today" = 0, "Minutes Online Today" = 0, "Minutes in Voice Chat Today" = 0')
            print("Reset daily stats")

    @reset_daily_stats.before_loop
    async def before_reset_daily_stats(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def track_activity(self):
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.status != discord.Status.offline and not member.bot:
                    user_id = str(member.id)
                    username = member.name
                    existing_user = self.fetch_query('SELECT 1 FROM user_info WHERE ID = ?', (user_id,))
                    if not existing_user:
                        self.execute_query('''
                        INSERT INTO user_info (ID, Username, Level, Points, Coins)
                        VALUES (?, ?, 1, 0, 0)''', (user_id, username))
                        self.execute_query('''
                        INSERT INTO user_stats (ID, Username, "Total Messages Sent", "Total Characters Typed", "Total Minutes Online", "Total Minutes in Voice Chat", "Last Daily", "Last Loan Disbursement", "Voice Join Time")
                        VALUES (?, ?, 0, 0, 0, 0, NULL, NULL, NULL)''', (user_id, username))
                        self.execute_query('''
                        INSERT INTO daily_stats (ID, Username, "Points Today", "Messages Sent Today", "Characters Typed Today", "Minutes Online Today", "Minutes in Voice Chat Today")
                        VALUES (?, ?, 0, 0, 0, 0, 0)''', (user_id, username))
                    self.execute_query('UPDATE user_stats SET "Total Minutes Online" = "Total Minutes Online" + ? WHERE ID = ?', (ONLINE_POINTS, user_id))
                    self.execute_query('UPDATE daily_stats SET "Minutes Online Today" = "Minutes Online Today" + ? WHERE ID = ?', (ONLINE_POINTS, user_id))

    def update_user_activity(self, user, points=0, coins=0):
        user_id = str(user.id)
        username = user.name
        existing_user = self.fetch_query('SELECT 1 FROM user_info WHERE ID = ?', (user_id,))
        if not existing_user:
            self.execute_query('''
            INSERT INTO user_info (ID, Username, Level, Points, Coins)
            VALUES (?, ?, 1, 0, 0)''', (user_id, username))
            self.execute_query('''
            INSERT INTO user_stats (ID, Username, "Total Messages Sent", "Total Characters Typed", "Total Minutes Online", "Total Minutes in Voice Chat", "Last Daily", "Last Loan Disbursement", "Voice Join Time")
            VALUES (?, ?, 0, 0, 0, 0, NULL, NULL, NULL)''', (user_id, username))
            self.execute_query('''
            INSERT INTO daily_stats (ID, Username, "Points Today", "Messages Sent Today", "Characters Typed Today", "Minutes Online Today", "Minutes in Voice Chat Today")
            VALUES (?, ?, 0, 0, 0, 0, 0)''', (user_id, username))
        self.execute_query('UPDATE user_info SET Points = Points + ?, Coins = Coins + ? WHERE ID = ?', (points, coins, user_id))
        self.execute_query('UPDATE daily_stats SET "Points Today" = "Points Today" + ? WHERE ID = ?', (points, user_id))

    async def announce_level_up_in_main_chat(self, user, previous_level, new_level):
        main_channel = discord.utils.get(user.guild.text_channels, name='licker-talk')
        if main_channel:
            await main_channel.send(f"{user.mention} has leveled up from Level {previous_level} to Level {new_level}. Congratulations, Gilligano!")
            await main_channel.send(f"To celebrate, here's a gift!  Generating..")

            generated_coins = random.randint(0, 15000)
            digits = str(generated_coins)

            accumulated_digits = ""

            for digit in digits:
                accumulated_digits += digit
                await main_channel.send(f"{accumulated_digits}")
                await asyncio.sleep(0.5)

            await main_channel.send(f"{digits} {coin_icon}")

            user_id = str(user.id)
            self.execute_query('UPDATE user_info SET Coins = Coins + ? WHERE ID = ?', (generated_coins, user_id))

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
        username = user.name
        existing_user = self.fetch_query('SELECT 1 FROM user_info WHERE ID = ?', (user_id,))
        if not existing_user:
            self.execute_query('''
            INSERT INTO user_info (ID, Username, Level, Points, Coins)
            VALUES (?, ?, 1, 0, 0)''', (user_id, username))
            self.execute_query('''
            INSERT INTO user_stats (ID, Username, "Total Messages Sent", "Total Characters Typed", "Total Minutes Online", "Total Minutes in Voice Chat", "Last Daily", "Last Loan Disbursement", "Voice Join Time")
            VALUES (?, ?, 0, 0, 0, 0, NULL, NULL, NULL)''', (user_id, username))
            self.execute_query('''
            INSERT INTO daily_stats (ID, Username, "Points Today", "Messages Sent Today", "Characters Typed Today", "Minutes Online Today", "Minutes in Voice Chat Today")
            VALUES (?, ?, 0, 0, 0, 0, 0)''', (user_id, username))
        self.execute_query('UPDATE user_info SET Coins = Coins + ? WHERE ID = ?', (coins, user_id))

    def transfer_coins(self, from_user, to_user, amount):
        from_user_id = str(from_user.id)
        to_user_id = str(to_user.id)

        if not self.fetch_query('SELECT 1 FROM user_info WHERE ID = ?', (from_user_id,)) or not self.fetch_query('SELECT 1 FROM user_info WHERE ID = ?', (to_user_id,)):
            return False, "User data not found."

        from_user_balance = self.fetch_query('SELECT Coins FROM user_info WHERE ID = ?', (from_user_id,))[0][0]
        if from_user_balance < amount:
            return False, "Insufficient balance."

        self.execute_query('UPDATE user_info SET Coins = Coins - ? WHERE ID = ?', (amount, from_user_id))
        self.execute_query('UPDATE user_info SET Coins = Coins + ? WHERE ID = ?', (amount, to_user_id))

        return True, f"Transferred {amount} coins from {from_user.name} to {to_user.name}."

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            self.update_user_activity(message.author, points=MESSAGE_POINTS)
            self.execute_query('UPDATE user_stats SET "Total Messages Sent" = "Total Messages Sent" + 1, "Total Characters Typed" = "Total Characters Typed" + ? WHERE ID = ?', (len(message.content), str(message.author.id)))
            self.execute_query('UPDATE daily_stats SET "Messages Sent Today" = "Messages Sent Today" + 1, "Characters Typed Today" = "Characters Typed Today" + ? WHERE ID = ?', (len(message.content), str(message.author.id)))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot:
            user_id = str(member.id)
            username = member.name
            if before.channel is None and after.channel is not None:
                # User has joined a voice channel
                print(f"{member.name} has joined a voice channel.")
                self.execute_query('UPDATE user_stats SET "Voice Join Time" = ? WHERE ID = ?', (datetime.now().timestamp(), user_id))

            elif before.channel is not None and after.channel is None:
                # User has left a voice channel
                join_time = self.fetch_query('SELECT "Voice Join Time" FROM user_stats WHERE ID = ?', (user_id,))[0][0]
                if join_time:
                    time_spent = datetime.now().timestamp() - join_time
                    points_earned = int(time_spent / 60) * VOICE_CHAT_POINTS
                    print(f"{member.name} has left the voice channel. Points earned: {points_earned}.")
                    self.update_user_activity(member, points=points_earned)
                    self.execute_query('UPDATE user_stats SET "Total Minutes in Voice Chat" = "Total Minutes in Voice Chat" + ?, "Voice Join Time" = NULL WHERE ID = ?', (int(time_spent / 60), user_id))
                    self.execute_query('UPDATE daily_stats SET "Minutes in Voice Chat Today" = "Minutes in Voice Chat Today" + ? WHERE ID = ?', (int(time_spent / 60), user_id))

    def get_statistics(self, user_id):
        return {
            'user_info': self.fetch_query('SELECT * FROM user_info WHERE ID = ?', (user_id,)),
            'user_stats': self.fetch_query('SELECT * FROM user_stats WHERE ID = ?', (user_id,)),
            'daily_stats': self.fetch_query('SELECT * FROM daily_stats WHERE ID = ?', (user_id,))
        }
    
    def get_coins(self, user_id):
        balance = self.fetch_query('SELECT Coins FROM user_info WHERE ID = ?', (user_id,))
        return balance[0][0] if balance else 0
    
    def get_level(self, user_id):
        level = self.fetch_query('SELECT Level FROM user_info WHERE ID = ?', (user_id,))
        return level[0][0] if level else 0

    def get_points(self, user_id):
        points = self.fetch_query('SELECT Points FROM user_info WHERE ID = ?', (user_id,))
        return points[0][0] if points else 0
    
    def update_coins(self, user_id, amount):
        current_balance = self.get_coins(user_id)

        new_balance = current_balance + amount

        if new_balance < 0:
            new_balance = 0

        self.execute_query('UPDATE user_info SET Coins = ? WHERE ID = ?', (new_balance, user_id))

        return new_balance
    
    def update_points(self, user_id, amount):
        current_balance = self.get_points(user_id)

        new_balance = current_balance + amount

        if new_balance < 0:
            new_balance = 0

        self.execute_query('UPDATE user_info SET Points = ? WHERE ID = ?', (new_balance, user_id))

        return new_balance
    
    def get_top_users_by_coins(self):
        return self.fetch_query('SELECT ID, Username, Coins FROM user_info ORDER BY Coins DESC LIMIT 10')
    
    def get_points_leaderboard(self):
        return self.fetch_query('SELECT ID, Username, Level, Points, Coins FROM user_info ORDER BY Points DESC LIMIT 10')

    def get_from_database(self, user_id, data_item):
        query_switch = {
            "Total Minutes in Voice Chat": 'Select "Total Minutes in Voice Chat" FROM user_stats WHERE ID = ?',
            "Total Minutes Online": 'Select "Total Minutes Online" FROM user_stats WHERE ID = ?',
            "Total Messages Sent": 'Select "Total Messages Sent" FROM user_stats WHERE ID = ?',
            "Total Characters Typed": 'Select "Total Characters Typed" FROM user_stats WHERE ID = ?',
        }
        
        query = query_switch.get(data_item)

        if query:
            result = self.fetch_query(query, (user_id,))
            return result[0][0] if result else 0
        else:
            return None

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

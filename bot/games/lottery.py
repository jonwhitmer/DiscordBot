import os, random, json, math, asyncio, logging
from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks
from settings.settings import load_settings

logging.basicConfig(level=logging.INFO)

TICKET_COST = 100

settings = load_settings()
coin_icon = settings['coin_icon']

class Lottery:
    def __init__(self, bot):
        self.bot = bot  # Set the bot for the lottery.
        self.check_lottery_draw.start()  # Starting the task that checks the lottery draw time.
        self.initial_pot = 30000  # Initial pot amount
        self.LOTTERY_FILE = 'data/games/lottery/lottery.json'

    def load_lottery_data(self):
        if not os.path.exists(self.LOTTERY_FILE):
            data = {'total_tickets': 0, 'participants': {}, 'current_pot': self.initial_pot}
            self.save_lottery_data(data)
        else:
            with open(self.LOTTERY_FILE, 'r') as file:
                data = json.load(file)
                if 'total_tickets' not in data:
                    data['total_tickets'] = 0
                if 'participants' not in data:
                    data['participants'] = {}
                if 'current_pot' not in data:
                    data['current_pot'] = self.initial_pot
        return data

    def save_lottery_data(self, data):
        with open(self.LOTTERY_FILE, 'w') as file:
            json.dump(data, file, indent=4)

    def get_current_lottery_pot(self):
        data = self.load_lottery_data()
        return data.get('current_pot', self.initial_pot)

    def add_tickets(self, user_id, ticket_count):
        data = self.load_lottery_data()
        if user_id not in data['participants']:
            data['participants'][user_id] = 0
        data['participants'][user_id] += ticket_count
        data['total_tickets'] += ticket_count
        data['current_pot'] += ticket_count * TICKET_COST
        self.save_lottery_data(data)

    def draw_winner(self):
        data = self.load_lottery_data()
        if data['total_tickets'] > 0:
            tickets = [user_id for user_id, count in data['participants'].items() for _ in range(count)]
            winner = random.choice(tickets)
            current_pot = data['current_pot']
            data['participants'] = {}
            data['total_tickets'] = 0
            data['current_pot'] = self.initial_pot
            self.save_lottery_data(data)
            return winner, current_pot
        return None, 0

    @tasks.loop(minutes=1)
    async def check_lottery_draw(self):
        data = self.load_lottery_data()
        channel = self.bot.get_channel(1252055670778368013)
        now = datetime.now(timezone.utc)
        logging.info(f"Current UTC time: {now}")
        if now.hour == 3 and now.minute == 0:
            logging.info("It's time to announce the winner!")
            await self.announce_winner()
        elif (now.hour == 16 and now.minute == 0) or (now.hour == 19 and now.minute == 0) or (now.hour == 1 and now.minute == 0): 
            await channel.send(f"Remember that 11 PM, the lottery will be drawn!  Type `!enterlottery` to buy tickets.")
            await channel.send(f"Current Pot: {data['current_pot']} {coin_icon}")

    async def announce_winner(self):
        data = self.load_lottery_data()
        if not data['participants']:
            logging.info("No participants in the lottery.")
            return

        channel = self.bot.get_channel(1252055670778368013)

        message = await channel.send("Today's Lottery Winner: ...")

        start_time = datetime.now(timezone.utc)
        duration = 60
        end_time = start_time + timedelta(seconds=duration)

        initial_sleep_time = 1
        final_sleep_time = 3
        total_steps = 1000

        current_step = 0
        while datetime.now(timezone.utc) < end_time:
            participant = random.choice(list(data['participants'].items()))
            user_id, tickets = participant
            ticket_number = random.choice(list(range(tickets)))
            member = await self.bot.fetch_user(user_id)
            await message.edit(content=f"Picking Lottery Winner... {member.display_name} (Ticket #{ticket_number})")

            sleep_time = initial_sleep_time + (final_sleep_time - initial_sleep_time) * (1 - math.exp(-current_step / total_steps))
            await asyncio.sleep(sleep_time)

            current_step += 1

        winner_id, current_pot = self.draw_winner()
        winner = await self.bot.fetch_user(winner_id)
        await message.edit(content=f"Today's Lottery Winner: {winner.display_name} (Ticket #{ticket_number})")
        await channel.send(content=f"{winner.display_name} has won {current_pot} {coin_icon}!")

        # Update the winner's activity
        activity_tracker = self.bot.get_cog('ActivityTracker')
        if winner:
            activity_tracker.update_user_activity(winner, coins=current_pot)
            await channel.send(content=f"Congratulations {winner.display_name}! Your new balance is {activity_tracker.get_statistics(str(winner.id)).get('coins', 0)} {coin_icon}.")
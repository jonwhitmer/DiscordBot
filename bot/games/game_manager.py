import discord, asyncio, json, logging
from discord.ext import commands
from discord.ext.commands import CommandOnCooldown
from .duel import Duel
from .blackjack import BlackjackGame
from .lottery import Lottery
from .dealerpoker import DealerPoker
from .gifthunt import GiftHunt
from .slots import SlotMachine
from settings.settings import load_settings

logging.basicConfig(level=logging.INFO)

# Load game settings from a JSON file
with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

BOT_TESTING_MODE = game_settings['game']['bot_testing_mode']  # Whether bot testing mode is enabled
if BOT_TESTING_MODE:
    POKER_MIN_PLAYERS = 1
    POKER_MAX_PLAYERS = 1

settings = load_settings()
coin_icon = settings['coin_icon']

TICKET_COST = 100

class GameManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.duels = {}
        self.blackjack_games = {}
        self.dealerpoker_games = {}
        self.slot_games = {}
        self.gifthunt_games = {}
        self.lottery = Lottery(bot)
        self.load_game_data()

    def load_game_data(self):
        try:
            with open('data/games/game_data.json', 'r') as file:
                self.game_data = json.load(file)
        except FileNotFoundError:
            self.game_data = self.initialize_game_data()

    def save_game_data(self):
        with open('game_data.json', 'w') as file:
            json.dump(self.game_data, file, indent=4)

    def update_game_stats(self, game, key, value):
        if game in self.game_data:
            if key in self.game_data[game]:
                self.game_data[game][key] += value
            else:
                self.game_data[game][key] = value
        else:
            self.game_data[game] = {}
            self.game_data[game][key] = value
        self.save_game_data()   

    async def CoinsAreOut(self, ctx, user_id):
        ActivityTracker = self.bot.get_cog('ActivityTracker')
        if ActivityTracker.get_coins(user_id) == 0:
            await ctx.send(f"You are out of coins.  Get a job or don't gamble.")
            return True
        elif ActivityTracker.get_coins(user_id) < 0:
            print("ERROR: Under 0?")
            return True
        else:
            return False

    @commands.command(name='accept')
    async def accept_duel(self, ctx):
        if ctx.author.id not in self.duels:
            return

        duel = self.duels[ctx.author.id]
        duel.generate_letter()
        await ctx.send(f"The duel between {self.bot.get_user(duel.player1).mention} and {self.bot.get_user(duel.player2).mention} has begun! The challenge is to type as many words as you can that start with '{duel.letter}'. The duel will continue until one player's health reaches zero. Type your words separated by spaces.")

        await self.handle_duel(ctx, duel)

    @commands.command(name='blackjack')
    @commands.cooldown(1, 60, commands.BucketType.channel)
    async def blackjack(self, ctx):
        user_id = ctx.author.id

        if ctx.channel.id != 1268242188328763474 and ctx.channel.id != 1259664562924552213:
            await ctx.send("Please utilize the <#1268242188328763474> channel to use the `!blackjack` command.")
            return
        
        if await self.CoinsAreOut(ctx, user_id) == True:
            return
        
        ActivityTracker = self.bot.get_cog('ActivityTracker')
        user_id = str(ctx.author.id)
        current_coins = ActivityTracker.get_coins(user_id)

        await ctx.send(f"You have {current_coins} {coin_icon}. How many {coin_icon} would you like to bet?")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        while True:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                bet = int(msg.content)
                if bet < 500:
                    await ctx.send(f"Bet must be at least 500 {coin_icon}. You have 30 seconds to respond accurately.")
                elif bet > 0 and bet <= current_coins:
                    break
                else:
                    await ctx.send(f"Invalid response. Bet must be a positive number and less than or equal to your balance ({current_coins} {coin_icon}). You have 30 seconds to respond accurately.")
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond! Please use !blackjack again.")
                return

        reduction_amt = -(bet)
        ActivityTracker.update_coins(ctx.author.id, reduction_amt)

        game = BlackjackGame(ctx.author, self.bot)
        await game.start_game(bet)
        self.blackjack_games[ctx.author.id] = game

        await game.send_hand(ctx)

    @commands.command(name='hit')
    async def hit(self, ctx):
        game = self.blackjack_games.get(ctx.author.id)
        if game:
            await game.hit(ctx)

    @commands.command(name='stand')
    async def stand(self, ctx):
        game = self.blackjack_games.get(ctx.author.id)
        if game:
            await game.stand(ctx)

    # Command to enter the lottery
    @commands.command(name='enterlottery')
    async def enter_lottery(self, ctx):
        user_id = str(ctx.author.id)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        current_lottery_pot = self.lottery.get_current_lottery_pot()
        await ctx.send(f"Each ticket is worth {TICKET_COST} {coin_icon}. How many tickets would you like to buy? Current Lottery Pot: {current_lottery_pot} {coin_icon}")

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=50.0)
            num_tickets = int(msg.content)
            cost = num_tickets * TICKET_COST

            await ctx.send(f"Are you sure you want to purchase {num_tickets} tickets for {cost} {coin_icon}? Say `!accept` if you wish to proceed.")

            msg = await self.bot.wait_for('message', check=check, timeout=50.0)
            if msg.content.lower() == '!accept':
                ActivityTracker = self.bot.get_cog('ActivityTracker')
                user_balance = ActivityTracker.get_coins(user_id)

                if user_balance < cost:
                    await ctx.send(f"{ctx.author.mention}, you do not have enough {coin_icon} to buy {num_tickets} tickets. Your current balance is {user_balance} {coin_icon}.")
                    return

                ActivityTracker.update_coins(ctx.author.id, -(cost))
                self.lottery.add_tickets(user_id, num_tickets)
                total_tickets = self.lottery.load_lottery_data()['participants'][user_id]

                current_lottery_pot = self.lottery.get_current_lottery_pot()
                await ctx.send(f"Purchase Successful. Check back at 11 PM EST for the lottery results. You now have a total of {total_tickets} tickets in the lottery. \nYour {coin_icon} Balance: {user_balance - cost} {coin_icon}, Current Lottery Pot: {current_lottery_pot} {coin_icon}")
            else:
                await ctx.send("Purchase cancelled")
        except ValueError:
            await ctx.send("Invalid number of tickets.")
        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond.")

    @commands.command(name='lotterystatus')
    async def lottery_status(self, ctx):
        data = self.lottery.load_lottery_data()
        total_tickets = data['total_tickets']
        participants = len(data['participants'])
        current_lottery_pot = self.lottery.get_current_lottery_pot()
        await ctx.send(f"__**Current Lottery Status:**__\nTotal Tickets Sold: {total_tickets}\nNumber of Participants: {participants}\nCurrent Lottery Pot: {current_lottery_pot} {coin_icon}")

    @commands.command(name='dealerpoker', help='Starts a dealer vs. player poker game')
    @commands.cooldown(1, 50, commands.BucketType.channel)
    async def start_dealer_poker(self, ctx):
        user_id = ctx.author.id

        if ctx.channel.id != 1268244378787254354 and ctx.channel.id != 1259664562924552213:
            await ctx.send("Please utilize the <#1268244378787254354> channel to use the `!dealerpoker` command.")
            return
        
        if ctx.channel.id in self.dealerpoker_games:
            await ctx.send("A dealer poker game is already running in this channel!")
            return
        
        if await self.CoinsAreOut(ctx, user_id) == True:
            return


        self.dealerpoker_games[ctx.channel.id] = True

        try:
            poker_game = DealerPoker(ctx, self.bot)
            await poker_game.start_game()
        finally:
            self.dealerpoker_games.pop(ctx.channel.id, None)
        
    @commands.command(name='gifthunt', help='Starts a dealer vs. player poker game')
    @commands.cooldown(1, 120, commands.BucketType.channel)
    async def start_gifthunt(self, ctx):
        user_id = ctx.author.id

        if ctx.channel.id != 1272829974478585889 and ctx.channel.id != 1259664562924552213:
            await ctx.send("Please utilize the <#1272829974478585889> channel to use the `!gifthunt` command.")
            return
        
        if ctx.channel.id in self.gifthunt_games:
            await ctx.send("A gift hunt game is already running in this channel!")
            return
        
        if await self.CoinsAreOut(ctx, user_id) == True:
            return

        self.gifthunt_games[ctx.channel.id] = True

        try:
            gift_hunt = GiftHunt(self.bot, ctx)
            await gift_hunt.start_game()
        finally:
            self.gifthunt_games.pop(ctx.channel.id, None)

    @commands.command(name='slots')
    @commands.cooldown(1, 45, commands.BucketType.channel)
    async def play_slots(self, ctx):
        user_id = ctx.author.id

        if ctx.channel.id != 1269351770107285575 and ctx.channel.id != 1259664562924552213:
            await ctx.send("Please utilize the <#1269351770107285575> channel to use the `!slots` command.")
            return
        
        if ctx.channel.id in self.slot_games:
            await ctx.send("A slot game is already running in this channel!")
            return
        
        if await self.CoinsAreOut(ctx, user_id) == True:
            return
    
        self.slot_games[ctx.channel.id] = True
        
        try:
            slots = SlotMachine(ctx, self.bot)
            await slots.start_game()
        finally:
            self.slot_games.pop(ctx.channel.id, None)

    @play_slots.error
    async def play_slots_error(self, ctx, error):
        if isinstance(error, CommandOnCooldown):
            await ctx.send(f"`!slots` is on cooldown.  Please wait {error.retry_after:.2f} seconds.")

    @start_dealer_poker.error
    async def start_dealer_poker_error(self, ctx, error):
        if isinstance(error, CommandOnCooldown):
            await ctx.send(f"`!dealerpoker` is on cooldown.  Please wait {error.retry_after:.3f} seconds.")

    @blackjack.error
    async def blackjack_error(self, ctx, error):
        if isinstance(error, CommandOnCooldown):
            await ctx.send(f"`!blackjack` is on cooldown.  Please wait {error.retry_after:.2f} seconds.")

    @start_gifthunt.error
    async def start_gifthunt_error(self, ctx, error):
        if isinstance(error, CommandOnCooldown):
            await ctx.send(f"`!gifthunt` is on cooldown.  Please wait {error.retry_after:.2f} seconds.")

async def setup(bot):
    await bot.add_cog(GameManager(bot))

import discord, asyncio, json, logging
from discord.ext import commands
from .duel import Duel
from .blackjack import BlackjackGame
from .lottery import Lottery
from .poker import PokerGame
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

class CommandHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.duels = {}
        self.blackjack_games = {}
        self.poker_games = {}
        self.lottery = Lottery(bot)

    @commands.command(name='challenge')
    async def challenge(self, ctx, opponent_name: str):
        opponent = self.find_member(ctx.guild, opponent_name)
        if opponent is None:
            await ctx.send(f"Could not find a unique member with the name '{opponent_name}'. Please specify a more exact name or use mention.")
            return

        if ctx.author.id in self.duels or opponent.id in self.duels:
            await ctx.send("One of the players is already in a duel!")
            return

        self.duels[ctx.author.id] = Duel(ctx.author.id, opponent.id)
        self.duels[opponent.id] = self.duels[ctx.author.id]

        if opponent == self.bot.user and BOT_TESTING_MODE:
            await self.accept_duel(ctx)
        else:
            await ctx.send(f"{ctx.author.mention} has challenged {opponent.mention} to a duel! Use `!accept` to accept the challenge.")

    @commands.command(name='accept')
    async def accept_duel(self, ctx):
        if ctx.author.id not in self.duels:
            return

        duel = self.duels[ctx.author.id]
        duel.generate_letter()
        await ctx.send(f"The duel between {self.bot.get_user(duel.player1).mention} and {self.bot.get_user(duel.player2).mention} has begun! The challenge is to type as many words as you can that start with '{duel.letter}'. The duel will continue until one player's health reaches zero. Type your words separated by spaces.")

        await self.handle_duel(ctx, duel)

    @commands.command(name='blackjack')
    async def blackjack(self, ctx):
        activity_tracker = self.bot.get_cog('ActivityTracker')
        stats = activity_tracker.get_statistics(str(ctx.author.id))
        current_coins = stats.get('coins', 0)

        await ctx.send(f"You have {current_coins} {coin_icon}. How many {coin_icon} would you like to bet?")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        while True:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                bet = int(msg.content)
                if bet > 0 and bet <= current_coins:
                    break
                else:
                    await ctx.send(f"Invalid response. Bet must be a positive number and less than or equal to your balance ({current_coins} {coin_icon}). You have 30 seconds to respond accurately.")
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond! Please use !blackjack again.")
                return

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

    @commands.command(name='peek')
    async def peek(self, ctx):
        # Ensure the author is part of an active poker game
        for game in self.poker_games.values():
            if ctx.author in game.players:
                await game.peek(ctx)
                return
        await ctx.send(f"{ctx.author.mention}, you are not part of an active poker game!")

    def find_member(self, guild, name):
        members = [member for member in guild.members if member.display_name.lower() == name.lower()]
        if len(members) == 1:
            return members[0]
        return None
    
    @commands.command(name='poker')
    async def start_poker(self, ctx):
        if ctx.author.id in self.poker_games:
            await ctx.send("You are already in a game!")
            return

        activity_tracker = self.bot.get_cog('ActivityTracker')
        stats = activity_tracker.get_statistics(str(ctx.author.id))
        current_coins = stats.get('coins', 0)

        await ctx.send(f"You have {current_coins} {coin_icon}. How many {coin_icon} would you like to set as the buy-in amount for the game?")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        while True:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                buy_in = int(msg.content)
                if buy_in > 0 and buy_in <= current_coins:
                    break
                else:
                    await ctx.send(f"Invalid response. Buy-in must be a positive number and less than or equal to your balance ({current_coins} {coin_icon}). You have 30 seconds to respond accurately.")
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond! Please use !poker again.")
                return

        game = PokerGame(ctx, self.bot, buy_in)
        self.poker_games[ctx.author.id] = game
        try:
            await game.start_game()
        finally:
            del self.poker_games[ctx.author.id]

        @commands.command(name='join poker')
        async def join_poker(self, ctx):
            if ctx.author.id not in self.poker_games:
                await ctx.send("You need to start a game first using !poker.")
                return
            game = self.poker_games[ctx.author.id]
            await game.collect_players()

    @commands.command(name='peek')
    async def peek(self, ctx):
        # Ensure the author is part of an active poker game
        for game in self.poker_games.values():
            if ctx.author in game.players:
                await game.peek(ctx)
                return
        await ctx.send(f"{ctx.author.mention}, you are not part of an active poker game!")

    @commands.command(name='forcestart')
    async def forcestart(self, ctx):
        # Ensure the author is part of an active poker game
        game = self.poker_games.get(ctx.author.id)
        if not game:
            await ctx.send(f"{ctx.author.mention}, you are not hosting any poker game!")
            return

        if len(game.players) >= game.POKER_MIN_PLAYERS:
            await ctx.send("Minimum player requirements met. Starting the game now!")
            await game.start_game()
        else:
            await ctx.send(f"Not enough players to start the game. Minimum required is {game.POKER_MIN_PLAYERS}.")

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
                activity_tracker = self.bot.get_cog('ActivityTracker')
                user_data = activity_tracker.get_statistics(user_id)
                user_balance = user_data.get('coins', 0)

                if user_balance < cost:
                    await ctx.send(f"{ctx.author.mention}, you do not have enough {coin_icon} to buy {num_tickets} tickets. Your current balance is {user_balance} {coin_icon}.")
                    return

                activity_tracker.update_user_activity(ctx.author, coins=-cost)
                self.lottery.add_tickets(user_id, num_tickets)
                total_tickets = self.lottery.load_lottery_data()['participants'][user_id]

                current_lottery_pot = self.lottery.get_current_lottery_pot()
                await ctx.send(f"Purchase Successful. Check back at 11 PM EST for the lottery results. You now have a total of {total_tickets} tickets in the lottery. \nYour {coin_icon} Balance: {user_balance - cost} {coin_icon}, Current Lottery Pot: {current_lottery_pot} {coin_icon}")
            else:
                await ctx.send("Purchase canceled.")
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


async def setup(bot):
    await bot.add_cog(CommandHandler(bot))

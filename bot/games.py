# bot/games.py

# Games played in the discord server from bot

from datetime import timedelta
import random  # Importing the random module to use for shuffling and generating random letters
import aiohttp  # Importing aiohttp for making asynchronous HTTP requests
import os  # Importing os for file operations
from PIL import Image  # Importing PIL (Pillow) for image processing
import json  # Importing json to read configuration settings from a file
import discord
import shutil
import io
from io import BytesIO  # Importing BytesIO for handling image data in memory
import asyncio
from discord.ext import commands
from discord import app_commands
from settings.settings import load_settings
import itertools

# Load game settings from a JSON file
with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

# Blackjack settings
CARD_VALUES = game_settings['blackjack']['card_values']  # Dictionary of card values
SUITS = game_settings['blackjack']['suits']  # List of suits
DECK = [f'{value}_of_{suit}' for suit in SUITS for value in CARD_VALUES.keys()]  # List of all cards in the deck
DECK_IMAGES_FOLDER = 'utils/images/deckofcards'
DUMP_IMAGES_FOLDER = 'utils/images/blackjackdump'

# Duel settings
DUEL_WIN_POINTS = game_settings['duel']['win_points']  # Points awarded for winning a duel
DUEL_WIN_COINS = game_settings['duel']['win_coins']  # Coins awarded for winning a duel

# Poker settings
POKER_WIN_POINTS = game_settings['poker']['win_points']
POKER_PREFLOP_MAX_BET = game_settings['poker']['preflop_max_bet']
POKER_MIN_PLAYERS = game_settings['poker']['min_players']
POKER_MAX_PLAYERS = game_settings['poker']['max_players']
DUMP_IMAGES_FOLDER_POKER = 'utils/images/pokerdump'

# Game Settings
BOT_TESTING_MODE = game_settings['game']['bot_testing_mode']  # Whether bot testing mode is enabled
if BOT_TESTING_MODE:
    POKER_MIN_PLAYERS = 1
    POKER_MAX_PLAYERS = 1

settings = load_settings()
coin_icon = settings['coin_icon']

# Class for handling duel game logic
class Duel:
    def __init__(self, player1, player2):
        self.player1 = player1  # ID of player 1
        self.player2 = player2  # ID of player 2
        self.health = {player1: 100, player2: 100}  # Initial health for both players
        self.letter = None  # The current letter for the duel
        self.used_words = set()  # Set of words that have already been used

    def generate_letter(self):
        self.letter = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')  # Generate a random letter

    async def is_valid_word(self, word):
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}"  # URL to check if the word is valid
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return resp.status == 200  # Return True if the word is valid

    def calculate_damage(self, words):
        valid_words = [word for word in words if word.lower().startswith(self.letter.lower()) and word.lower() not in self.used_words]
        self.used_words.update(word.lower() for word in valid_words)  # Add valid words to the set of used words
        return sum(len(word) for word in valid_words)  # Calculate damage as the sum of the lengths of valid words

    def get_winner(self):
        if self.health[self.player1] <= 0:
            return self.player2  # Player 2 wins if player 1's health is 0 or less
        elif self.health[self.player2] <= 0:
            return self.player1  # Player 1 wins if player 2's health is 0 or less
        return None  # No winner if both players have health above 0

    def adjust_health(self, player_id, damage):
        self.health[player_id] = max(self.health[player_id] - damage, 0)  # Reduce health by the damage amount, but not below 0

# Class for handling blackjack game logic
class BlackjackGame:
    def __init__(self, player, bot):
        self.deck = [f'{value}{suit}' for value in '23456789JQKA' for suit in 'CDHS']
        self.deck.extend([f'10{suit}' for suit in 'CDHS'])
        random.shuffle(self.deck)
        self.player = player
        self.bot = bot
        self.player_hand = []
        self.dealer_hand = []
        self.player_points = 0
        self.dealer_points = 0
        self.bet = 0

    async def deal_initial_cards(self):
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.player_points = self.calculate_hand_value(self.player_hand)
        self.dealer_points = self.calculate_hand_value(self.dealer_hand)

    def calculate_hand_value(self, hand):
        value = 0
        aces = 0
        for card in hand:
            card_value = card[:-1]  # Get the card value without the suit
            if card_value.isdigit():
                value += int(card_value)
            elif card_value in ['J', 'Q', 'K']:
                value += 10
            else:
                value += 11
                aces += 1
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    async def start_game(self, bet):
        self.bet = bet
        self.deck = [f'{value}{suit}' for value in '23456789JQKA' for suit in 'CDHS']
        self.deck.extend([f'10{suit}' for suit in 'CDHS'])
        random.shuffle(self.deck)
        await self.deal_initial_cards()

    async def player_hit(self):
        card = self.deck.pop()
        self.player_hand.append(card)
        self.player_points = self.calculate_hand_value(self.player_hand)
        return card

    async def dealer_play(self):
        while self.dealer_points < 17:
            card = self.deck.pop()
            self.dealer_hand.append(card)
            self.dealer_points = self.calculate_hand_value(self.dealer_hand)
        return self.dealer_hand

    def get_game_result(self):
        if self.player_points > 21:
            return "bust"
        elif self.dealer_points > 21 or self.player_points > self.dealer_points:
            return "win"
        elif self.player_points == self.dealer_points:
            return "push"
        else:
            return "lose"

    async def create_hand_image(self, hand, reveal_dealer=False):
        card_images = []
        for card in hand:
            if isinstance(card, dict) and card.get('value') == 'back':
                card_image_path = os.path.join(DECK_IMAGES_FOLDER, 'back.png')
            else:
                card_value = card[:-1]  # Extract the value part of the card string
                card_suit = card[-1].upper()  # Extract the suit part of the card string
                if card_value == '10':  # Check for '10' separately
                    card_image_path = os.path.join(DECK_IMAGES_FOLDER, '10', f'10{card_suit}.png')
                else:
                    card_value = card_value[0].upper()
                    card_image_path = os.path.join(DECK_IMAGES_FOLDER, card_value, f'{card_value}{card_suit}.png')
            card_images.append(card_image_path)
        return card_images



    async def concatenate_images(self, image_paths, filename):
        images = [Image.open(path) for path in image_paths]
        widths, heights = zip(*(img.size for img in images))
        total_width = sum(widths)
        max_height = max(heights)
        new_image = Image.new('RGB', (total_width, max_height))

        x_offset = 0
        for img in images:
            new_image.paste(img, (x_offset, 0))
            x_offset += img.size[0]

        output_path = os.path.join(DUMP_IMAGES_FOLDER, filename)
        new_image.save(output_path)

        return output_path


    async def hit(self, ctx):
        card = await self.player_hit()
        await self.send_hand(ctx)

        if self.player_points > 21:
            await self.end_game(ctx, "bust")

    async def stand(self, ctx):
        dealer_hand = await self.dealer_play()
        await self.send_hand(ctx, reveal_dealer=True)

        result = self.get_game_result()
        await self.end_game(ctx, result)

    async def end_game(self, ctx, result):
        activity_tracker = self.bot.get_cog('ActivityTracker')
        if result == "win":
            payout = self.bet * 2
            activity_tracker.update_user_activity(ctx.author, points=DUEL_WIN_POINTS, coins=self.bet)
            await ctx.send(f"Congratulations {ctx.author.mention}, you win! You have been awarded {DUEL_WIN_POINTS} points and {payout} {coin_icon}.")
        elif result == "bust":
            payout = -(self.bet)
            activity_tracker.update_user_activity(ctx.author, points=DUEL_WIN_POINTS, coins=payout)
            await ctx.send(f"Sorry {ctx.author.mention}, you busted! You lost {self.bet} {coin_icon}.")
        elif result == "lose":
            payout = -(self.bet)
            activity_tracker.update_user_activity(ctx.author, points=DUEL_WIN_POINTS, coins=payout)
            await ctx.send(f"Sorry {ctx.author.mention}, you lose! You lost {self.bet} {coin_icon}.")
        elif result == "push":
            await ctx.send(f"It's a push, {ctx.author.mention}. Your bet of {self.bet} {coin_icon} has been returned.")

        await self.cleanup_images()
        del self.bot.get_cog('CommandHandler').blackjack_games[ctx.author.id]

    async def send_hand(self, ctx, reveal_dealer=False):
        player_images = await self.create_hand_image(self.player_hand)
        dealer_hand = self.dealer_hand if reveal_dealer else self.dealer_hand[:1] + [{'value': 'back', 'suit': ''}]
        dealer_images = await self.create_hand_image(dealer_hand)

        concatenated_player_image = await self.concatenate_images(player_images, f'blackjack_{ctx.author.id}_player_hand.png')
        concatenated_dealer_image = await self.concatenate_images(dealer_images, f'blackjack_{ctx.author.id}_dealer_hand.png')

        player_hand_embed = discord.File(concatenated_player_image, filename="player_hand.png")
        dealer_hand_embed = discord.File(concatenated_dealer_image, filename="dealer_hand.png")

        embed = discord.Embed(title="Blackjack")
        embed.add_field(name="Your Hand", value=f"Points: {self.player_points}", inline=True)
        embed.add_field(name="Dealer's Hand", value=f"Points: {self.dealer_points if reveal_dealer else '?'}", inline=True)
        embed.set_image(url=f"attachment://player_hand.png")
        embed.set_thumbnail(url=f"attachment://dealer_hand.png")

        await ctx.send(embed=embed, files=[player_hand_embed, dealer_hand_embed])


    async def cleanup_images(self):
        for filename in os.listdir(DUMP_IMAGES_FOLDER):
            file_path = os.path.join(DUMP_IMAGES_FOLDER, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)

class PokerGame:
    def __init__(self, ctx, bot, buy_in):
        self.bot = bot  # The bot instance
        self.ctx = ctx  # The context from Discord
        self.buy_in = buy_in  # The buy-in amount for the game
        self.players = []  # List to store players
        self.betting_order = []  # Order in which players will bet
        self.current_bet = 0  # Current bet amount
        self.pot = 0  # Total pot amount
        self.current_player_index = 0  # Index to track the current player
        self.community_cards = []  # List to store community cards
        self.player_hands = {}  # Dictionary to store each player's hand
        self.player_balances = {}  # Dictionary to store each player's balance
        self.all_in_players = set()  # Set to track players who are all-in
        self.DECK_OF_CARDS_FOLDER = 'utils/images/deckofcards'  # Folder for card images
        self.DUMP_IMAGES_FOLDER = 'utils/images/pokerdump'  # Folder for dumping images
        self.game_cancelled = False  # Flag to check if the game is cancelled

    async def start_game(self):
        await self.collect_players()  # Collect players for the game
        if len(self.players) < POKER_MIN_PLAYERS:  # Check if there are enough players
            await self.ctx.send("Not enough players to start the game. Refunding buy-ins.")
            await self.refund_buy_ins()  # Refund the buy-ins if not enough players
            return

        self.betting_order = self.players[:]  # Set the betting order to the list of players
        random.shuffle(self.betting_order)  # Shuffle the betting order
        await self.deal_cards()  # Deal the initial cards to the players
        await self.betting_round(pre_flop=True)  # Run the first betting round (pre-flop)
        await self.reveal_community_cards(3)  # Reveal the flop (3 community cards)
        await self.betting_round()  # Run the second betting round
        await self.reveal_community_cards(1)  # Reveal the turn (1 community card)
        await self.betting_round()  # Run the third betting round
        await self.reveal_community_cards(1)  # Reveal the river (1 community card)
        await self.betting_round()  # Run the final betting round
        await self.showdown()  # Determine the winner and show the final hands

    async def collect_players(self):
        await self.ctx.send(f"A new poker game is starting with a buy-in of {self.buy_in} coins! Type `!join poker` to join. You have 2 minutes to join. The host can type `!cancel poker` to cancel the game or `!forcestart` to start the game if the minimum player requirements are met.")

        activity_tracker = self.bot.get_cog('ActivityTracker')
        player_coins = activity_tracker.get_statistics(str(self.ctx.author.id)).get('coins', 0)
        if player_coins < self.buy_in:
            await self.ctx.send(f"{self.ctx.author.mention}, you do not have enough coins to start the game.")
            return

        self.players.append(self.ctx.author)
        self.player_balances[self.ctx.author] = self.buy_in
        activity_tracker.update_user_activity(self.ctx.author, coins=-(self.buy_in))
        await self.display_player_list()

        def join_check(m):
            return m.content.lower() == "!join poker" and m.channel == self.ctx.channel

        def cancel_check(m):
            return m.content.lower() == "!cancel poker" and m.channel == self.ctx.channel and m.author == self.ctx.author

        def forcestart_check(m):
            return m.content.lower() == "!forcestart" and m.channel == self.ctx.channel and m.author == self.ctx.author

        end_time = discord.utils.utcnow() + timedelta(minutes=2)
        warning_times = [60, 30, 10]  # Times to send warnings in seconds
        sent_warnings = set()

        while True:
            remaining_time = (end_time - discord.utils.utcnow()).total_seconds()

            # Send warning messages
            for warning in warning_times:
                if remaining_time <= warning and warning not in sent_warnings:
                    await self.ctx.send(f"{int(warning)} seconds remaining to join the game!")
                    sent_warnings.add(warning)

            if remaining_time <= 0:
                break

            try:
                done, pending = await asyncio.wait(
                    [asyncio.create_task(self.bot.wait_for('message', check=join_check)), 
                    asyncio.create_task(self.bot.wait_for('message', check=cancel_check)),
                    asyncio.create_task(self.bot.wait_for('message', check=forcestart_check))],
                    timeout=1,
                    return_when=asyncio.FIRST_COMPLETED
                )

                if not done:
                    continue

                msg = done.pop().result()

                if msg.content.lower() == "!cancel poker":
                    await self.cancel_game()
                    return

                if msg.content.lower() == "!forcestart":
                    if len(self.players) >= 2:
                        await self.ctx.send("Minimum player requirements met. Starting the game now!")
                        break
                    else:
                        await self.ctx.send(f"Not enough players to start the game. Minimum required is 2.")
                        continue

                if msg.author in self.players:
                    await self.ctx.send(f"{msg.author.mention}, you are already in the game!")
                    continue

                player_coins = activity_tracker.get_statistics(str(msg.author.id)).get('coins', 0)
                if player_coins < self.buy_in:
                    await self.ctx.send(f"{msg.author.mention}, you do not have enough coins to join the game.")
                    continue

                self.players.append(msg.author)
                self.player_balances[msg.author] = self.buy_in
                activity_tracker.update_user_activity(msg.author, coins=-self.buy_in)
                await self.ctx.send(f"{msg.author.mention} has joined the Poker session!")
                await self.display_player_list()

                if len(self.players) > 8:
                    await self.ctx.send(f"MAX PLAYER EXCEEDED ERROR! The game has been cancelled.")
                    await self.cancel_game()
                    return

                if len(self.players) == 8:
                    await self.ctx.send("Maximum number of players reached. Starting the game now!")
                    break
            except asyncio.TimeoutError:
                continue

        if len(self.players) < 2:
            await self.ctx.send("Not enough players to start the game. Refunding buy-ins.")
            for player in self.players:
                activity_tracker.update_user_activity(player, coins=self.buy_in)
                await self.ctx.send(f"{player.mention}, you have been refunded {self.buy_in} coins.")
            return

        await self.deal_cards()

    async def cancel_game(self):
        activity_tracker = self.bot.get_cog('ActivityTracker')
        for player in self.players:
            activity_tracker.update_user_activity(player, coins=self.buy_in)
            await self.ctx.send(f"{player.mention}, you have been refunded {self.buy_in} coins.")
        await self.ctx.send("The poker game has been cancelled by the host.")

    async def deal_cards(self):
        self.deck = [f'{value}{suit}' for value in '23456789JQKA' for suit in 'CDHS']
        self.deck.extend([f'10{suit}' for suit in 'CDHS'])
        random.shuffle(self.deck)
        for player in self.players:
            self.player_hands[player] = [self.deck.pop(), self.deck.pop()]
            await self.send_hand(self.ctx, player)
    
    async def send_hand(self, ctx, player, reveal=False):
        hand = self.player_hands[player]
        card_images = [await self.get_card_image(card) for card in hand]
        concatenated_image_path = await self.concatenate_images(card_images, f'poker_{player.id}_hand.png')
        file = discord.File(concatenated_image_path, filename="hand.png")

        if reveal:
            embed = discord.Embed(title=f"{player.display_name}'s Hand")
        else:
            embed = discord.Embed(title="Your Hand")
        
        embed.set_image(url="attachment://hand.png")
        await ctx.send(file=file, embed=embed, ephemeral=True)

    async def get_card_image(self, card):
            card_value = card[:-1]
            card_suit = card[-1].upper()
            if card_value == '10':
                card_image_path = os.path.join(self.DECK_OF_CARDS_FOLDER, '10', f'10{card_suit}.png')
            else:
                card_value = card_value[0].upper()
                card_image_path = os.path.join(self.DECK_OF_CARDS_FOLDER, card_value, f'{card_value}{card_suit}.png')
            return card_image_path
    
    async def concatenate_images(self, image_paths, filename):
        images = [Image.open(path) for path in image_paths]
        widths, heights = zip(*(img.size for img in images))
        total_width = sum(widths)
        max_height = max(heights)
        new_image = Image.new('RGB', (total_width, max_height))

        x_offset = 0
        for img in images:
            new_image.paste(img, (x_offset, 0))
            x_offset += img.size[0]

        output_path = os.path.join(self.DUMP_IMAGES_FOLDER, filename)
        new_image.save(output_path)

        return output_path

    async def betting_round(self, pre_flop=False):
        self.current_bet = 0 if pre_flop else self.current_bet
        for player in self.betting_order:
            if player in self.all_in_players:
                continue
            await self.prompt_player_action(player)

    async def prompt_player_action(self, player):
        if self.current_bet == 0:
            await self.ctx.send(f"{player.mention}, it's your turn. You can `!check`, `check`, `!fold`, `fold`, `!raise`, `raise`, or `!allin`, `allin`. Your balance: {self.player_balances[player]} {coin_icon}. Pot: {self.pot} {coin_icon}.")
            valid_actions = ['!check', 'check', '!fold', 'fold', '!raise', 'raise', '!allin', 'allin']
        else:
            await self.ctx.send(f"{player.mention}, it's your turn. You can `!call`, `call`, `!fold`, `fold`, `!raise`, `raise`, or `!allin`, `allin`. Your balance: {self.player_balances[player]} {coin_icon}. Pot: {self.pot} {coin_icon}.")
            valid_actions = ['!call', 'call', '!fold', 'fold', '!raise', 'raise', '!allin', 'allin']

        def check(m):
            return m.author == player and m.channel == self.ctx.channel and m.content.lower() in valid_actions

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=120)
            action = msg.content.lower().lstrip('!')
            if action == 'check':
                await self.check(player)
            elif action == 'call':
                await self.call(player)
            elif action == 'fold':
                await self.fold(player)
            elif action == 'raise':
                await self.raise_bet(player)
            elif action == 'allin':
                await self.allin(player)
        except asyncio.TimeoutError:
            await self.fold(player)

    @app_commands.command(name="peek", description="Peek at your hand in the current poker game")
    async def peek(self, interaction: discord.Interaction):
        player = interaction.user
        if player not in self.players:
            await interaction.response.send_message(f"{player.mention}, you are not part of this game!", ephemeral=True)
            return

        await self.send_hand(self.ctx, player)

    async def check(self, player):
        await self.ctx.send(f"{player.mention} checks.")

    async def call(self, player):
        call_amount = self.current_bet - self.player_balances[player]
        if self.player_balances[player] < call_amount:
            await self.allin(player)
        else:
            self.player_balances[player] -= call_amount
            self.pot += call_amount
            await self.ctx.send(f"{player.mention} calls {call_amount} coins. Pot is now {self.pot} {coin_icon}.")

    async def fold(self, player):
        self.betting_order.remove(player)
        await self.ctx.send(f"{player.mention} folds.")

    async def raise_bet(self, player):
        await self.ctx.send(f"{player.mention}, how much would you like to raise? Type an amount or `!allin` or `allin`.")
        def check(m):
            return m.author == player and m.channel == self.ctx.channel
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=120)
            if msg.content.lower().lstrip('!') == 'allin':
                await self.allin(player)
            else:
                try:
                    raise_amount = int(msg.content)
                    if raise_amount > self.player_balances[player]:
                        await self.ctx.send(f"You don't have enough {coin_icon} to raise that amount.")
                        await self.raise_bet(player)
                    else:
                        self.current_bet += raise_amount
                        self.player_balances[player] -= raise_amount
                        self.pot += raise_amount
                        await self.ctx.send(f"{player.mention} raises by {raise_amount} {coin_icon}. Current bet is now {self.current_bet} {coin_icon}. Pot is now {self.pot} {coin_icon}.")
                except ValueError:
                    await self.ctx.send(f"{msg.content} is not a valid amount. Please enter a valid number or type `!allin` or `allin`.")
                    await self.raise_bet(player)
        except asyncio.TimeoutError:
            await self.fold(player)
            await self.fold(player)

    async def allin(self, player):
        allin_amount = self.player_balances[player]
        self.all_in_players.add(player)
        self.player_balances[player] = 0
        self.pot += allin_amount
        await self.ctx.send(f"{player.mention} goes all-in with {allin_amount} {coin_icon}. Pot is now {self.pot} {coin_icon}.")

    async def reveal_community_cards(self, num):
        for _ in range(num):
            self.deck.pop()  # Burn card
            self.community_cards.append(self.deck.pop())
        cards = [await self.get_card_image(card) for card in self.community_cards]
        concatenated_image_path = await self.concatenate_images(cards, 'community_cards.png')
        file = discord.File(concatenated_image_path, filename="community_cards.png")

        embed = discord.Embed(title="Community Cards")
        embed.set_image(url="attachment://community_cards.png")
        await self.ctx.send(file=file, embed=embed)

    async def showdown(self):
        await self.ctx.send("Showdown! Revealing hands...")
        hands = []
        for player in self.betting_order:
            hand = self.player_hands[player] + self.community_cards
            best_hand = self.get_best_hand(hand)
            hands.append((player, best_hand))
            await self.reveal_hand(player, best_hand)

        if not hands:
            await self.ctx.send("No hands to compare, ending showdown.")
            return

        winner = max(hands, key=lambda h: self.hand_rank(h[1]))[0]
        await self.ctx.send(f"{winner.mention} wins the pot of {self.pot} {coin_icon}!")

    async def display_player_list(self):
        if self.players:
            player_list = "\n".join([player.mention for player in self.players])
            embed = discord.Embed(title="Current Player List", description=player_list, color=discord.Color.blue())
            await self.ctx.send(embed=embed)
        else:
            await self.ctx.send("No players have joined yet.")

    def hand_rank(self, hand):
        """
        Determine the rank of a given poker hand.

        :param hand: List of 5 card strings (e.g., ['2H', '3D', '5S', '9C', 'KD'])
        :return: Tuple representing the hand rank and its components for comparison
        """

        # Define card ranks and their corresponding values
        ranks = '2345678910JQKA'
        values = {r: i for i, r in enumerate(ranks.split(), start=2)}

        # Get the numeric value of each card in the hand
        hand_ranks = sorted(
            [values['10'] if card[:-1] == '10' else values[card[0]] for card in hand],
            reverse=True
        )

        # Check for flush (all cards have the same suit)
        is_flush = len(set(card[-1] for card in hand)) == 1

        # Check for straight (consecutive card values)
        is_straight = len(set(hand_ranks)) == 5 and (hand_ranks[0] - hand_ranks[-1] == 4)

        # Special case: A-5 straight
        if hand_ranks == [14, 5, 4, 3, 2]:
            hand_ranks = [5, 4, 3, 2, 1]
            is_straight = True

        # Count the occurrences of each rank in the hand
        rank_counter = {r: hand_ranks.count(r) for r in hand_ranks}
        rank_values = sorted(((count, rank) for rank, count in rank_counter.items()), reverse=True)

        # Determine the rank of the hand
        if is_straight and is_flush:
            return (8, hand_ranks[0])  # Straight flush
        elif rank_values[0][0] == 4:
            return (7, rank_values[0][1], rank_values[1][1])  # Four of a kind
        elif rank_values[0][0] == 3 and rank_values[1][0] == 2:
            return (6, rank_values[0][1], rank_values[1][1])  # Full house
        elif is_flush:
            return (5, hand_ranks)  # Flush
        elif is_straight:
            return (4, hand_ranks[0])  # Straight
        elif rank_values[0][0] == 3:
            return (3, rank_values[0][1], hand_ranks)  # Three of a kind
        elif rank_values[0][0] == 2 and rank_values[1][0] == 2:
            return (2, rank_values[0][1], rank_values[1][1], hand_ranks)  # Two pair
        elif rank_values[0][0] == 2:
            return (1, rank_values[0][1], hand_ranks)  # One pair
        else:
            return (0, hand_ranks)  # High card
        
    def get_best_hand(self, hand):
        """
        From the 7 cards, choose the best 5-card hand.
        """
        all_combinations = itertools.combinations(hand, 5)
        best_hand = max(all_combinations, key=self.hand_rank)
        return best_hand

    async def reveal_hand(self, player, hand):
        cards = [await self.get_card_image(card) for card in hand]
        embed = discord.Embed(title=f"{player.display_name}'s Hand")
        for card in cards:
            embed.set_image(url=card)
        await self.ctx.send(embed=embed)

class CommandHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.duels = {}
        self.blackjack_games = {}
        self.poker_games = {}

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
            await ctx.send(f"{ctx.author.mention} has challenged {opponent.mention} to a duel! Use !accept to accept the challenge.")

    @commands.command(name='accept')
    async def accept_duel(self, ctx):
        if ctx.author.id not in self.duels:
            await ctx.send("You have not been challenged to a duel!")
            return

        duel = self.duels[ctx.author.id]
        duel.generate_letter()
        await ctx.send(f"The duel between {self.bot.get_user(duel.player1).mention} and {self.bot.get_user(duel.player2).mention} has begun! The challenge is to type as many words as you can that start with '{duel.letter}'. The duel will continue until one player's health reaches zero. Type your words separated by spaces.")

        await self.handle_duel(ctx, duel)

    async def handle_duel(self, ctx, duel):
        def check(m):
            return m.channel == ctx.channel and m.author.id in [duel.player1, duel.player2]

        while True:
            msg = await self.bot.wait_for('message', check=check)
            damage = await self.process_message(msg, duel)
            opponent_id = duel.player1 if msg.author.id == duel.player2 else duel.player2
            duel.adjust_health(opponent_id, damage)

            embed = discord.Embed(
                title="Duel Status",
                description=f"{self.bot.get_user(duel.player1).mention} vs {self.bot.get_user(duel.player2).mention}",
                color=discord.Color.red()
            )
            embed.add_field(name=f"{self.bot.get_user(duel.player1).display_name} HP", value=duel.health[duel.player1])
            embed.add_field(name=f"{self.bot.get_user(duel.player2).display_name} HP", value=duel.health[duel.player2])
            await ctx.send(embed=embed)

            winner_id = duel.get_winner()
            if winner_id:
                winner = self.bot.get_user(winner_id)
                await ctx.send(f"{winner.mention} wins the duel!")
                activity_tracker = self.bot.get_cog('ActivityTracker')
                activity_tracker.update_user_activity(winner, points=DUEL_WIN_POINTS, coins=DUEL_WIN_COINS)
                await ctx.send(f"{winner.mention} has been awarded {DUEL_WIN_POINTS} points and {DUEL_WIN_COINS} {coin_icon}! Total {coin_icon}: {activity_tracker.activity_data[str(winner.id)]['coins']}")
                
                del self.duels[duel.player1]
                del self.duels[duel.player2]
                return

    async def process_message(self, msg, duel):
        words = msg.content.split()
        valid_words = []
        for word in words:
            if await duel.is_valid_word(word):
                if word.lower() not in duel.used_words:
                    valid_words.append(word)
                else:
                    await msg.channel.send(f"The word '{word}' has already been used.")
            else:
                await msg.channel.send(f"The word '{word}' is not a valid word.")
        return duel.calculate_damage(valid_words)

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

async def setup(bot):
    await bot.add_cog(CommandHandler(bot))
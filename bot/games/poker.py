import discord, random, os, asyncio, itertools, json
from discord.ext import commands
from PIL import Image
from settings.settings import load_settings
from datetime import timedelta

with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

settings = load_settings()
coin_icon = settings['coin_icon']

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
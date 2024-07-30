import random, os, discord, asyncio, json
from PIL import Image
from discord.ext import commands
from settings.settings import load_settings

with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

settings = load_settings()
coin_icon = settings['coin_icon']

CARD_VALUES = game_settings['blackjack']['card_values']  # Dictionary of card values
SUITS = game_settings['blackjack']['suits']  # List of suits
DECK = [f'{value}_of_{suit}' for suit in SUITS for value in CARD_VALUES.keys()]  # List of all cards in the deck
DECK_IMAGES_FOLDER = 'utils/images/deckofcards'
DUMP_IMAGES_FOLDER = 'utils/images/blackjackdump'

BLACKJACK_WIN_POINTS = 100
BLACKJACK_LOSS_POINTS = 20
BLACKJACK_PUSH_POINTS = 45

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
            activity_tracker.update_user_activity(ctx.author, points=BLACKJACK_WIN_POINTS, coins=payout)
            await ctx.send(f"Congratulations {ctx.author.mention}, you win! You have been awarded {BLACKJACK_WIN_POINTS} points and {payout} {coin_icon}.")
        elif result == "bust":
            activity_tracker.update_user_activity(ctx.author, points=BLACKJACK_LOSS_POINTS)
            await ctx.send(f"Sorry {ctx.author.mention}, you busted! You lost {self.bet} {coin_icon}.")
        elif result == "lose":
            activity_tracker.update_user_activity(ctx.author, points=BLACKJACK_LOSS_POINTS)
            await ctx.send(f"Sorry {ctx.author.mention}, you lose! You lost {self.bet} {coin_icon}.")
        elif result == "push":
            activity_tracker.update_user_activity(ctx.author, points=BLACKJACK_PUSH_POINTS, coins=self.bet)
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
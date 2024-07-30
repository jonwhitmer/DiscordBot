import discord, random, os, asyncio, json, asyncio, itertools
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from settings.settings import load_settings

with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

settings = load_settings()
coin_icon = settings['coin_icon']

# Poker Settings
POKER_WIN_POINTS = 120


class DealerPoker:
    def __init__(self, ctx, bot):
        self.bot = bot
        self.ctx = ctx
        self.player = ctx.author
        self.dealer_hand = []
        self.player_hands = {}
        self.community_cards = []
        self.DECK_OF_CARDS_FOLDER = 'utils/images/deckofcards'
        self.DUMP_IMAGES_FOLDER = 'utils/images/pokerdump'
        self.game_cancelled = False
        self.player_bet = 0
        self.ante = 0
        self.player_balance = 0

    async def start_game(self):
        await self.ask_for_ante()
        if self.game_cancelled:
            return
        
        await self.deal_initial_cards()
        await self.betting_round(pre_flop = True)
        await self.reveal_community_cards(3)
        await self.betting_round()
        await self.reveal_community_cards(1)
        await self.betting_round()
        await self.reveal_community_cards(1)
        await self.betting_round(final = True)
        await self.showdown()
        await self.cleanup()

    async def ask_for_ante(self):
        await self.ctx.send(f"{self.ctx.author.mention}, how many {coin_icon} would you like to ante?")

        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=120)
            self.ante = int(msg.content)
            activity_tracker = self.bot.get_cog('ActivityTracker')
            user_data = activity_tracker.get_statistics(str(self.player.id))
            player_coins = user_data.get('coins', 0)

            if player_coins < self.ante:
                await self.ctx.send(f"{self.ctx.author.mention}, you do not have enough {coin_icon} to ante that amount.")
                self.game_cancelled = True
                return
            
            activity_tracker.update_user_activity(self.ctx.author, coins=-(self.ante))
            self.player_balance = self.ante
            self.player_hands[self.ctx.author] = []
            await self.ctx.send(f"{self.ctx.author.mention}, you have anted {self.ante} {coin_icon}.  Starting Dealer Poker..")
        except asyncio.TimeoutError:
            await self.ctx.send(f"{self.ctx.author.mention} took too long to respond.  Game has been cancelled without refund.")
            self.game_cancelled = True
        except ValueError:
            await self.ctx.send(f"{msg.content} is not a valid number.  Game cancelled.")
            self.game_cancelled = True

    async def deal_initial_cards(self):
        self.deck = [f'{value}{suit}' for value in '23456789JQKA' for suit in 'CDHS']
        self.deck.extend([f'10{suit}' for suit in 'CDHS'])
        random.shuffle(self.deck)

        self.player_hands[self.player] = [self.deck.pop(), self.deck.pop()]
        await self.send_hand(self.ctx, self.player)

        self.dealer_hand = [self.deck.pop(), self.deck.pop()]

    async def betting_round(self, pre_flop=False, final=False):
        activity_tracker = self.bot.get_cog('ActivityTracker')
        user_data = activity_tracker.get_statistics(str(self.player.id))
        player_total_coins = int(user_data.get('coins', 0))

        max_bet = int(4 * self.ante if pre_flop else 1.5 * self.ante if final else 2 * self.ante)
        action_message = "you can `!check` or place a `!bet`" if not final else "you can `!fold` or place a `!bet`"
        await self.ctx.send(f"{self.ctx.author.mention}, {action_message} of {max_bet} {coin_icon}. Your current balance is {player_total_coins} {coin_icon}.")

        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel

        try:
            while True:
                msg = await self.bot.wait_for('message', check=check, timeout=120)
                content = msg.content.lower().split()
                
                if content[0] == '!check' and not final:
                    await self.ctx.send(f"{self.ctx.author.mention} checks.")
                    break  # Exit the loop as a valid action was taken

                elif content[0] == '!bet':
                    try:
                        bet_amount = max_bet if len(content) == 1 else int(content[1])

                        if bet_amount < 1 or bet_amount > max_bet:
                            await self.ctx.send(f"{self.ctx.author.mention}, invalid bet amount. Please bet up to {max_bet} {coin_icon}.")
                        elif bet_amount > player_total_coins:
                            await self.ctx.send(f"{self.ctx.author.mention}, you do not have enough balance to place this bet.")
                        else:
                            self.player_bet += bet_amount
                            player_total_coins -= bet_amount
                            activity_tracker.update_user_activity(self.ctx.author, coins=-bet_amount)
                            await self.ctx.send(f"{self.ctx.author.mention} places a bet of {bet_amount} {coin_icon}. Total bet: {self.player_bet} {coin_icon}. Current balance: {player_total_coins} {coin_icon}.")
                            break  # Exit the loop as a valid action was taken
                    except ValueError:
                        await self.ctx.send(f"{self.ctx.author.mention}, please enter a valid bet amount.")

                elif content[0] == '!fold' and final:
                    await self.ctx.send(f"{self.ctx.author.mention} folds. Game over.")
                    self.game_cancelled = True
                    return

                else:
                    await self.ctx.send("Invalid action. Please try again.")
        except asyncio.TimeoutError:
            await self.ctx.send(f"{self.ctx.author.mention} took too long to respond. Game over.")
            self.game_cancelled = True

    def get_max_bet(self, pre_flop, final):
        if pre_flop:
            return 4 * self.ante
        elif final:
            return 1 * self.ante
        return 2 * self.ante

    async def reveal_community_cards(self, num):
        for _ in range(num):
            self.deck.pop()  # Burn card
            self.community_cards.append(self.deck.pop())

        await self.display_community_cards()

    async def display_community_cards(self):
        cards = [await self.get_card_image(card) for card in self.community_cards]
        concatenated_image_path = await self.concatenate_images(cards, 'community_cards.png')
        file = discord.File(concatenated_image_path, filename="community_cards.png")

        embed = discord.Embed(title="Community Cards")
        embed.set_image(url="attachment://community_cards.png")
        await self.ctx.send(file=file, embed=embed)

    async def showdown(self):
        player_hand = self.player_hands[self.ctx.author]
        dealer_hand = self.dealer_hand
        player_best_hand = self.get_best_hand(player_hand + self.community_cards)
        dealer_best_hand = self.get_best_hand(dealer_hand + self.community_cards)

        player_rank = self.hand_rank(player_best_hand)
        dealer_rank = self.hand_rank(dealer_best_hand)
        if player_rank > dealer_rank:
            result = f"{self.ctx.author.mention} wins with {self.rank_description(player_rank)}!"
        elif player_rank < dealer_rank:
            result = f"The dealer wins with {self.rank_description(dealer_rank)}. Better luck next time!"
        else:
            result = "It's a tie!"

        # Create images for the showdown
        player_hand_image = await self.get_hand_image(player_hand)
        dealer_hand_image = await self.get_hand_image(dealer_hand)
        community_cards_image = await self.get_hand_image(self.community_cards)

        # Concatenate all parts into one image
        final_showdown_image = await self.concatenate_images([player_hand_image, community_cards_image, dealer_hand_image], 'final_showdown.png')

        # Send the result with the final image
        file = discord.File(final_showdown_image, filename="final_showdown.png")
        embed = discord.Embed(title="Final Showdown", description=result)
        embed.set_image(url="attachment://final_showdown.png")
        await self.ctx.send(file=file, embed=embed)

        # Clean up images
        for img_path in [player_hand_image, dealer_hand_image, community_cards_image, final_showdown_image]:
            os.remove(img_path)

    async def display_final_hands(self, player_hand, dealer_hand):
        player_hand_images = [await self.get_card_image(card) for card in player_hand]
        dealer_hand_images = [await self.get_card_image(card) for card in dealer_hand]

        # Create a combined image of the player and dealer hands
        player_hand_image = await self.concatenate_images(player_hand_images, 'player_final_hand.png')
        dealer_hand_image = await self.concatenate_images(dealer_hand_images, 'dealer_final_hand.png')

        embed = discord.Embed(title="Final Hands")
        embed.set_image(url="attachment://player_final_hand.png")
        player_file = discord.File(player_hand_image, filename="player_final_hand.png")
        dealer_file = discord.File(dealer_hand_image, filename="dealer_final_hand.png")

        msg = await self.ctx.send(file=player_file, embed=embed)

        # Wait and reveal the dealer's hand
        await asyncio.sleep(2)
        embed.set_image(url="attachment://dealer_final_hand.png")
        await msg.edit(embed=embed)
        await self.ctx.send(file=dealer_file)

    def rank_description(self, rank):
        descriptions = [
            "High Card", 
            "One Pair", 
            "Two Pair", 
            "Three of a Kind", 
            "Straight", 
            "Flush", 
            "Full House", 
            "Four of a Kind", 
            "Straight Flush", 
            "Royal Flush"
        ]
        return descriptions[rank[0]]

    async def get_hand_image(self, hand):
        cards = [await self.get_card_image(card) for card in hand]
        concatenated_image_path = await self.concatenate_images(cards, 'showdown_hand.png')
        return concatenated_image_path

    async def send_hand(self, ctx, player, reveal=False, dealer=False):
        hand = self.player_hands[player] if not dealer else self.dealer_hand
        card_images = [await self.get_card_image(card) for card in hand]
        concatenated_image_path = await self.concatenate_images(card_images, f'poker_{player.id}_hand.png')
        file = discord.File(concatenated_image_path, filename="hand.png")

        title = f"{player.display_name}'s Hand" if not dealer else "Dealer's Hand"
        embed = discord.Embed(title=title)
        embed.set_image(url="attachment://hand.png")
        await ctx.send(file=file, embed=embed)

    async def get_card_image(self, card):
        card_value = card[:-1]
        card_suit = card[-1].upper()
        if card_value == '10':
            card_image_path = os.path.join(self.DECK_OF_CARDS_FOLDER, '10', f'10{card_suit}.png')
        else:
            card_value = card_value[0].upper()
            card_image_path = os.path.join(self.DECK_OF_CARDS_FOLDER, card_value, f'{card_value}{card_suit}.png')
        return card_image_path

    async def concatenate_images(self, image_paths, filename, vertical=False):
        images = [Image.open(path) for path in image_paths]
        widths, heights = zip(*(img.size for img in images))
        
        if vertical:
            total_width = max(widths)
            total_height = sum(heights)
        else:
            total_width = sum(widths)
            total_height = max(heights)

        new_image = Image.new('RGB', (total_width, total_height))

        x_offset, y_offset = 0, 0
        for img in images:
            if vertical:
                new_image.paste(img, (0, y_offset))
                y_offset += img.size[1]
            else:
                new_image.paste(img, (x_offset, 0))
                x_offset += img.size[0]

        output_path = os.path.join(self.DUMP_IMAGES_FOLDER, filename)
        new_image.save(output_path)

        return output_path


    def hand_rank(self, hand):
        # Define ranks and handle '10' separately
        ranks = '23456789JQKA'
        values = {r: i for i, r in enumerate(ranks, start=2)}
        values['10'] = 10  # Explicitly add '10' to the values

        # Extract ranks and suits from hand
        hand_ranks = sorted([values[card[:-1]] for card in hand], reverse=True)
        suits = [card[-1] for card in hand]

        # Check for flush
        is_flush = len(set(suits)) == 1
        flush_ranks = [values[card[:-1]] for card in hand if card[-1] == suits[0]]
        flush_ranks.sort(reverse=True)

        # Check for straight within the flush cards
        is_straight_flush = len(set(flush_ranks)) == 5 and (flush_ranks[0] - flush_ranks[-1] == 4)

        # Special case: Ace can be low in a straight (A-2-3-4-5)
        if set(flush_ranks) == {14, 5, 4, 3, 2}:
            is_straight_flush = True
            flush_ranks = [5, 4, 3, 2, 1]

        # Check for Royal Flush
        if is_straight_flush and flush_ranks == [14, 13, 12, 11, 10]:
            return (9, flush_ranks)  # Royal Flush

        # Check for Straight Flush
        if is_straight_flush:
            return (8, flush_ranks)  # Straight Flush

        # Check for normal Straight
        is_straight = len(set(hand_ranks)) == 5 and (hand_ranks[0] - hand_ranks[-1] == 4)
        if set(hand_ranks) == {14, 5, 4, 3, 2}:
            is_straight = True
            hand_ranks = [5, 4, 3, 2, 1]

        # Other rankings
        rank_counter = {r: hand_ranks.count(r) for r in hand_ranks}
        rank_values = sorted(((count, rank) for rank, count in rank_counter.items()), reverse=True)

        # Four of a kind
        if rank_values[0][0] == 4:
            return (7, rank_values[0][1], rank_values[1][1])

        # Full house
        if rank_values[0][0] == 3 and rank_values[1][0] == 2:
            return (6, rank_values[0][1], rank_values[1][1])

        # Flush (not a straight flush)
        if is_flush:
            return (5, flush_ranks)

        # Straight (not a straight flush)
        if is_straight:
            return (4, hand_ranks)

        # Three of a kind
        if rank_values[0][0] == 3:
            return (3, rank_values[0][1], hand_ranks)

        # Two pair
        if rank_values[0][0] == 2 and rank_values[1][0] == 2:
            return (2, rank_values[0][1], rank_values[1][1], hand_ranks)

        # One pair
        if rank_values[0][0] == 2:
            return (1, rank_values[0][1], hand_ranks)

        # High card
        return (0, hand_ranks)

    def get_best_hand(self, hand):
        all_combinations = itertools.combinations(hand, 5)
        best_hand = max(all_combinations, key=self.hand_rank)
        return best_hand

    async def reveal_hand(self, player, hand, dealer=False):
        cards = [await self.get_card_image(card) for card in hand]
        concatenated_image_path = await self.concatenate_images(cards, f'poker_{player.id}_hand.png')
        file = discord.File(concatenated_image_path, filename="hand.png")

        title = f"{player.display_name}'s Hand" if not dealer else "Dealer's Hand"
        embed = discord.Embed(title=title)
        embed.set_image(url="attachment://hand.png")
        msg = await self.ctx.send(file=file, embed=embed)

        # Dramatic reveal of each card
        for i, card in enumerate(cards):
            await asyncio.sleep(1)  # Adding delay for dramatic effect
            if i < len(cards) - 1:
                await msg.edit(content=f"{player.display_name} reveals {card}.")
            else:
                await self.ctx.send(f"{player.display_name} reveals {card}.")

    async def create_final_showdown_image(self, player_hand, dealer_hand):
        # Get image paths for each hand and community cards
        player_hand_images = [await self.get_card_image(card) for card in player_hand]
        dealer_hand_images = [await self.get_card_image(card) for card in dealer_hand]
        community_cards_images = [await self.get_card_image(card) for card in self.community_cards]

        # Load all images
        player_imgs = [Image.open(img) for img in player_hand_images]
        dealer_imgs = [Image.open(img) for img in dealer_hand_images]
        community_imgs = [Image.open(img) for img in community_cards_images]

        # Determine maximum width and height for card images
        max_card_width = max(img.width for img in player_imgs + dealer_imgs + community_imgs)
        max_card_height = max(img.height for img in player_imgs + dealer_imgs + community_imgs)

        # Define spacing
        spacing = 10
        text_height = 30

        # Calculate total width and height
        total_width = max_card_width * max(len(player_imgs), len(dealer_imgs), len(community_imgs)) + spacing * 2
        total_height = max_card_height * 3 + text_height * 3 + spacing * 5

        # Create a new image
        combined_image = Image.new('RGB', (total_width, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(combined_image)
        font = ImageFont.truetype("arial.ttf", 20)  # You may need to specify the path to a font file

        # Draw Player's Hand
        draw.text((spacing, spacing), "Player's Hand", font=font, fill="black")
        y_offset = spacing + text_height
        x_offset = spacing
        for img in player_imgs:
            combined_image.paste(img, (x_offset, y_offset))
            x_offset += img.width + spacing

        # Draw Community Cards
        draw.text((spacing, y_offset + max_card_height + spacing), "Community Cards", font=font, fill="black")
        y_offset += max_card_height + spacing + text_height
        x_offset = spacing
        for img in community_imgs:
            combined_image.paste(img, (x_offset, y_offset))
            x_offset += img.width + spacing

        # Draw Dealer's Hand
        draw.text((spacing, y_offset + max_card_height + spacing), "Dealer's Hand", font=font, fill="black")
        y_offset += max_card_height + spacing + text_height
        x_offset = spacing
        for img in dealer_imgs:
            combined_image.paste(img, (x_offset, y_offset))
            x_offset += img.width + spacing

        # Save the combined image
        final_image_path = os.path.join(self.DUMP_IMAGES_FOLDER, 'final_showdown.png')
        combined_image.save(final_image_path)

        return final_image_path


    async def cleanup(self):
        """Clean up temporary images and reset state if needed."""
        for filename in os.listdir(self.DUMP_IMAGES_FOLDER):
            file_path = os.path.join(self.DUMP_IMAGES_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

    def cleanup_image(self, image_path):
        """Remove the image file after it's used."""
        try:
            os.remove(image_path)
        except Exception as e:
            print(f"Error deleting image {image_path}: {e}")


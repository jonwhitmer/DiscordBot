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
POKER_TIE_POINTS = 90
POKER_LOSS_POINTS = 30


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
        self.previous_community_cards_message = None
        self.game_cancelled = False
        self.raised = False
        self.player_bet = 0
        self.ante = 0
        self.bot_messages = []

    async def start_game(self):
        await self.ask_for_ante()
        if self.game_cancelled:
            return

        await self.deal_initial_cards()
        if self.game_cancelled:
            return

        await self.betting_round(stage='pre_flop')
        if self.game_cancelled:
            return

        await self.reveal_community_cards(3)
        if self.game_cancelled:
            return

        await self.betting_round(stage='flop')
        if self.game_cancelled:
            return

        await self.reveal_community_cards(1)
        if self.game_cancelled:
            return

        await self.betting_round(stage='turn')
        if self.game_cancelled:
            return

        await self.reveal_community_cards(1)
        if self.game_cancelled:
            return

        await self.betting_round(stage='river')
        if self.game_cancelled:
            return

        await self.showdown()
        if self.game_cancelled:
            return

        await self.cleanup()

    async def ask_for_ante(self):
        ActivityTracker = self.bot.get_cog('ActivityTracker')
        user_id = self.player.id
        await self.ctx.send(f"{self.ctx.author.mention}, how many {coin_icon} would you like to ante?  Current balance: {int(ActivityTracker.get_coins(user_id))} {coin_icon}")

        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=120)
            self.ante = int(msg.content)
            ActivityTracker = self.bot.get_cog('ActivityTracker')
            player_coins = ActivityTracker.get_coins(user_id)

            if player_coins < self.ante:
                await self.ctx.send(f"{self.ctx.author.mention}, you do not have enough {coin_icon} to ante that amount.")
                self.game_cancelled = True
                return
            
            ActivityTracker.update_coins(user_id, -(self.ante))
            self.player_bet = self.ante
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

    async def betting_round(self, stage='pre_flop'):
        ActivityTracker = self.bot.get_cog('ActivityTracker')
        user_id = self.player.id
        player_total_coins = int(ActivityTracker.get_coins(user_id))

        # Determine the max bet based on the game stage
        if stage == 'pre_flop':
            max_bet = self.ante * 4
        elif stage == 'flop':
            max_bet = self.ante * 2 + self.player_bet
        elif stage == 'turn':
            max_bet = int(self.ante * 1.75 + self.player_bet)
        elif stage == 'river':
            max_bet = int(self.ante * 1.35 + self.player_bet)
        else:
            max_bet = self.player_bet  # In case of an invalid stage, default to the current bet

        # Calculate the additional amount needed to reach the max bet
        additional_amount = max_bet - self.player_bet

        # Determine the action message based on the game stage
        if self.raised == True:
            await asyncio.sleep(2)
            return
        
        if stage == 'river':
            if additional_amount > player_total_coins:
                action_message = (f"you can `!fold` or go `!allin` with {player_total_coins} {coin_icon}.")
            else:
                action_message = (f"you can `!fold`, raise the `!bet` to {max_bet} {coin_icon} "
                                  f"({additional_amount} more).")
        else:
            action_message = (f"you can `!check` or raise the `!bet` to {max_bet} {coin_icon} "
                                f"({additional_amount} more).")

        # Send the message with the current bet, action options, and player's balance at the end
        message = await self.ctx.send(f"{self.ctx.author.mention}, the current bet is {self.player_bet} {coin_icon}. "
                            f"{action_message} Your current balance is {player_total_coins} {coin_icon}.")
        
        self.bot_messages.append(message)

        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel

        try:
            while True:
                msg = await self.bot.wait_for('message', check=check, timeout=50)
                content = msg.content.lower().split()
                
                if content[0] == '!check' and stage != 'river':
                    rsp_msg = await self.ctx.send(f"{self.ctx.author.mention} checks.")
                    self.bot_messages.append(rsp_msg)
                    break  # Exit the loop as a valid action was taken

                elif content[0] == '!fold' and stage == 'river':
                    await self.ctx.send(f"{self.ctx.author.mention} folds. Game over.")
                    await self.display_winner_if_folded()
                    self.game_cancelled = True
                    return

                elif content[0] == '!bet':
                    try:
                        bet_amount = max_bet if len(content) == 1 else int(content[1])

                        if bet_amount < self.player_bet or bet_amount > max_bet:
                            rsp_msg = await self.ctx.send(f"{self.ctx.author.mention}, invalid bet amount. Please bet between {self.player_bet} and {max_bet} {coin_icon}.")
                            self.bot_messages.append(rsp_msg)
                        elif additional_amount > player_total_coins:
                            rsp_msg = await self.ctx.send(f"{self.ctx.author.mention}, you do not have enough balance to place this bet.")
                            self.bot_messages.append(rsp_msg)
                        else:
                            self.player_bet = bet_amount  # Update player's total bet to include the new bet amount
                            player_total_coins -= additional_amount
                            ActivityTracker = self.bot.get_cog('ActivityTracker')
                            ActivityTracker.update_coins(user_id, -(additional_amount))
                            rsp_msg = await self.ctx.send(f"{self.ctx.author.mention} places a bet of {additional_amount} {coin_icon}. Total bet: {self.player_bet} {coin_icon}. Current balance: {player_total_coins} {coin_icon}.")
                            self.bot_messages.append(rsp_msg)
                            self.raised = True
                            break  # Exit the loop as a valid action was taken
                    except ValueError:
                        rsp_msg = await self.ctx.send(f"{self.ctx.author.mention}, please enter a valid bet amount.")
                        self.bot_messages.append(rsp_msg)
                
                elif content[0] == '!allin' and stage == 'river' and (additional_amount > player_total_coins):
                    if additional_amount > player_total_coins:
                        # Going all-in
                        additional_amount = player_total_coins
                        self.player_bet += player_total_coins
                        ActivityTracker.update_coins(user_id, -(player_total_coins))
                        rsp_msg = await self.ctx.send(f"{self.ctx.author.mention} goes all-in with {player_total_coins} {coin_icon}. Total bet: {self.player_bet} {coin_icon}.")
                        self.bot_messages.append(rsp_msg)
                        self.raised = True
                        break
                    else:
                        continue
                else:
                    rsp_msg = await self.ctx.send("Invalid action. Please try again.")
                    self.bot_messages.append(rsp_msg)
        except asyncio.TimeoutError:
            await self.ctx.send(f"{self.ctx.author.mention} took too long to respond. Game over.")
            self.game_cancelled = True

    async def display_winner_if_folded(self):
        # Simulate a showdown to determine who would have won
        player_hand = self.player_hands[self.ctx.author]
        dealer_hand = self.dealer_hand
        player_best_hand = self.get_best_hand(player_hand + self.community_cards)
        dealer_best_hand = self.get_best_hand(dealer_hand + self.community_cards)

        player_rank = self.hand_rank(player_best_hand)
        dealer_rank = self.hand_rank(dealer_best_hand)

        # Determine the winner based on ranks
        if player_rank > dealer_rank:
            result = f"Would have won: {self.ctx.author.display_name} with a {self.rank_description(player_rank)}"
        elif player_rank < dealer_rank:
            result = f"Would have won: Dealer with a {self.rank_description(dealer_rank)}"
        else:
            result = "It would have been a tie!"

        await asyncio.sleep(1)
        await self.ctx.send(f"**HYPOTHETICAL RESULT**")
        await asyncio.sleep(1)

        # Create and send Player's Hand embed
        player_hand_images = [await self.get_card_image(card) for card in player_hand]
        player_hand_image_path = await self.concatenate_images(player_hand_images, 'player_hand.png')
        player_hand_file = discord.File(player_hand_image_path, filename="player_hand.png")
        player_embed = discord.Embed(title="Player's Hand")
        player_embed.set_image(url="attachment://player_hand.png")
        await self.ctx.send(file=player_hand_file, embed=player_embed)

        await asyncio.sleep(2)

        # Create and send Community Cards embed
        community_cards_images = [await self.get_card_image(card) for card in self.community_cards]
        community_cards_image_path = await self.concatenate_images(community_cards_images, 'community_cards.png')
        community_cards_file = discord.File(community_cards_image_path, filename="community_cards.png")
        community_embed = discord.Embed(title="Community Cards")
        community_embed.set_image(url="attachment://community_cards.png")
        await self.ctx.send(file=community_cards_file, embed=community_embed)

        await asyncio.sleep(2)

        # Create and send Dealer's Hand embed
        dealer_hand_images = [await self.get_card_image(card) for card in dealer_hand]
        dealer_hand_image_path = await self.concatenate_images(dealer_hand_images, 'dealer_hand.png')
        dealer_hand_file = discord.File(dealer_hand_image_path, filename="dealer_hand.png")
        dealer_embed = discord.Embed(title="Dealer's Hand")
        dealer_embed.set_image(url="attachment://dealer_hand.png")
        await self.ctx.send(file=dealer_hand_file, embed=dealer_embed)

        await asyncio.sleep(3)

        # Send the result message
        await self.ctx.send(result)

        await self.clear_messages()

        # Clean up images
        os.remove(player_hand_image_path)
        os.remove(community_cards_image_path)
        os.remove(dealer_hand_image_path)

    async def reveal_community_cards(self, num):
        for _ in range(num):
            self.deck.pop()  # Burn card
            self.community_cards.append(self.deck.pop())

        await self.display_community_cards()

    async def display_community_cards(self):
        if self.previous_community_cards_message:
            await self.previous_community_cards_message.delete()
        
        message = await self.ctx.send("**|**")
        await asyncio.sleep(1)
        await message.edit(content="**| |**")
        await asyncio.sleep(1)
        await message.edit(content="**| | |**")
        await asyncio.sleep(1)
        
        await message.delete()

        cards = [await self.get_card_image(card) for card in self.community_cards]
        concatenated_image_path = await self.concatenate_images(cards, 'community_cards.png')
        file = discord.File(concatenated_image_path, filename="community_cards.png")

        embed = discord.Embed(title="Community Cards")
        embed.set_image(url="attachment://community_cards.png")
        
        self.previous_community_cards_message = await self.ctx.send(file=file, embed=embed)

    async def clear_messages(self):
        for message in self.bot_messages:
            try:
                await message.delete()
            except discord.NotFound:
                pass
        
        self.bot_messages.clear()
        await self.previous_community_cards_message.delete()

    async def showdown(self):
        player_hand = self.player_hands[self.ctx.author]
        dealer_hand = self.dealer_hand
        player_best_hand = self.get_best_hand(player_hand + self.community_cards)
        dealer_best_hand = self.get_best_hand(dealer_hand + self.community_cards)

        player_rank = self.hand_rank(player_best_hand)
        dealer_rank = self.hand_rank(dealer_best_hand)

        ActivityTracker = self.bot.get_cog('ActivityTracker')
        user_id = self.player.id

        if player_rank > dealer_rank:
            result = f"{self.ctx.author.mention} wins with a {self.rank_description(player_rank)} and has won {POKER_WIN_POINTS} points and {self.player_bet * 2} {coin_icon}!"
            payout = self.player_bet * 2
            ActivityTracker.update_coins(user_id, payout)
            ActivityTracker.update_points(user_id, POKER_WIN_POINTS)
        elif player_rank < dealer_rank:
            result = f"The dealer wins with a {self.rank_description(dealer_rank)}. Better luck next time! You have received {POKER_LOSS_POINTS} points."
            payout = 0
            ActivityTracker.update_coins(user_id, payout)
            ActivityTracker.update_points(user_id, POKER_LOSS_POINTS)
        else:
            result = f"It's a tie! Both you and the dealer have the same hand. You have received {POKER_TIE_POINTS} points, and your ante of {self.ante} {coin_icon} has been returned."
            payout = self.player_bet  # Usually, in a tie, the player gets their ante back or a portion of it
            ActivityTracker.update_coins(user_id, payout)
            ActivityTracker.update_points(user_id, POKER_TIE_POINTS)

        await asyncio.sleep(1)
        await self.ctx.send(f"**SHOWDOWN**")
        await asyncio.sleep(1)

        # Create and send Player's Hand embed
        player_hand_images = [await self.get_card_image(card) for card in player_hand]
        player_hand_image_path = await self.concatenate_images(player_hand_images, 'player_hand.png')
        player_hand_file = discord.File(player_hand_image_path, filename="player_hand.png")
        player_embed = discord.Embed(title="Player's Hand")
        player_embed.set_image(url="attachment://player_hand.png")
        await self.ctx.send(file=player_hand_file, embed=player_embed)

        await asyncio.sleep(2)

        # Create and send Community Cards embed
        community_cards_images = [await self.get_card_image(card) for card in self.community_cards]
        community_cards_image_path = await self.concatenate_images(community_cards_images, 'community_cards.png')
        community_cards_file = discord.File(community_cards_image_path, filename="community_cards.png")
        community_embed = discord.Embed(title="Community Cards")
        community_embed.set_image(url="attachment://community_cards.png")
        await self.ctx.send(file=community_cards_file, embed=community_embed)

        await asyncio.sleep(2)

        # Create and send Dealer's Hand embed
        dealer_hand_images = [await self.get_card_image(card) for card in dealer_hand]
        dealer_hand_image_path = await self.concatenate_images(dealer_hand_images, 'dealer_hand.png')
        dealer_hand_file = discord.File(dealer_hand_image_path, filename="dealer_hand.png")
        dealer_embed = discord.Embed(title="Dealer's Hand")
        dealer_embed.set_image(url="attachment://dealer_hand.png")
        await self.ctx.send(file=dealer_hand_file, embed=dealer_embed)

        await asyncio.sleep(3)

        # Send the result message
        await self.ctx.send(result)

        await self.clear_messages()

        # Clean up images
        os.remove(player_hand_image_path)
        os.remove(community_cards_image_path)
        os.remove(dealer_hand_image_path)

    async def display_final_hands(self, player_hand, dealer_hand):
        player_hand_images = [await self.get_card_image(card) for card in player_hand]
        dealer_hand_images = [await self.get_card_image(card) for card in dealer_hand]

        player_hand_image = await self.concatenate_images(player_hand_images, 'player_final_hand.png')
        dealer_hand_image = await self.concatenate_images(dealer_hand_images, 'dealer_final_hand.png')

        embed = discord.Embed(title="Final Hands")
        embed.set_image(url="attachment://player_final_hand.png")
        player_file = discord.File(player_hand_image, filename="player_final_hand.png")
        dealer_file = discord.File(dealer_hand_image, filename="dealer_final_hand.png")

        msg = await self.ctx.send(file=player_file, embed=embed)

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
        initial = await ctx.send(file=file, embed=embed)

        self.bot_messages.append(initial)

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
        # Define ranks and handle '10' separately using 'T'
        ranks = '23456789TJQKA'
        values = {r: i for i, r in enumerate(ranks, start=2)}
        values['T'] = 10

        # Extract ranks and suits from hand
        hand_ranks = sorted([values[card[:-1].replace('10', 'T')] for card in hand], reverse=True)
        suits = [card[-1] for card in hand]

        # Check for flush
        is_flush = len(set(suits)) == 1
        flush_ranks = hand_ranks if is_flush else []

        # Check for straight
        is_straight = len(set(hand_ranks)) == 5 and (hand_ranks[0] - hand_ranks[-1] == 4)
        # Special case: Ace can be low in a straight (A-2-3-4-5)
        if set(hand_ranks) == {14, 5, 4, 3, 2}:
            is_straight = True
            hand_ranks = [5, 4, 3, 2, 1]

        # Check for other hands using rank counts
        rank_counter = {r: hand_ranks.count(r) for r in hand_ranks}
        rank_values = sorted(((count, rank) for rank, count in rank_counter.items()), reverse=True)

        # Determine the hand ranking
        if is_straight and is_flush:
            if hand_ranks == [14, 13, 12, 11, 10]:
                return (9, hand_ranks)  # Royal Flush
            return (8, hand_ranks)      # Straight Flush
        if rank_values[0][0] == 4:
            return (7, rank_values[0][1], rank_values[1][1])  # Four of a Kind
        if rank_values[0][0] == 3 and rank_values[1][0] == 2:
            return (6, rank_values[0][1], rank_values[1][1])  # Full House
        if is_flush:
            return (5, flush_ranks)  # Flush
        if is_straight:
            return (4, hand_ranks)   # Straight
        if rank_values[0][0] == 3:
            return (3, rank_values[0][1], rank_values[1][1])  # Three of a Kind
        if rank_values[0][0] == 2 and rank_values[1][0] == 2:
            return (2, rank_values[0][1], rank_values[1][1], rank_values[2][1])  # Two Pair
        if rank_values[0][0] == 2:
            return (1, rank_values[0][1], rank_values[1][1], rank_values[2][1], rank_values[3][1])  # One Pair
        return (0, hand_ranks)  # High Card

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

        # Create and send Player's Hand embed
        player_hand_image_path = await self.concatenate_images(player_hand_images, 'player_hand.png')
        player_hand_file = discord.File(player_hand_image_path, filename="player_hand.png")
        player_embed = discord.Embed(title="Player's Hand")
        player_embed.set_image(url="attachment://player_hand.png")
        await self.ctx.send(file=player_hand_file, embed=player_embed)

        # Create and send Community Cards embed
        community_cards_image_path = await self.concatenate_images(community_cards_images, 'community_cards.png')
        community_cards_file = discord.File(community_cards_image_path, filename="community_cards.png")
        community_embed = discord.Embed(title="Community Cards")
        community_embed.set_image(url="attachment://community_cards.png")
        await self.ctx.send(file=community_cards_file, embed=community_embed)

        # Create and send Dealer's Hand embed
        dealer_hand_image_path = await self.concatenate_images(dealer_hand_images, 'dealer_hand.png')
        dealer_hand_file = discord.File(dealer_hand_image_path, filename="dealer_hand.png")
        dealer_embed = discord.Embed(title="Dealer's Hand")
        dealer_embed.set_image(url="attachment://dealer_hand.png")
        await self.ctx.send(file=dealer_hand_file, embed=dealer_embed)

        # Determine winner and hand rank description
        player_best_hand = self.get_best_hand(player_hand + self.community_cards)
        dealer_best_hand = self.get_best_hand(dealer_hand + self.community_cards)
        player_rank = self.hand_rank(player_best_hand)
        dealer_rank = self.hand_rank(dealer_best_hand)

        if player_rank > dealer_rank:
            result = f"{self.ctx.author.display_name} wins with a {self.rank_description(player_rank)}!"
        elif player_rank < dealer_rank:
            result = f"The dealer wins with a {self.rank_description(dealer_rank)}. Better luck next time!"
        else:
            result = "It's a tie!"

        # Send the result message
        await self.ctx.send(result)

        # Clean up images
        os.remove(player_hand_image_path)
        os.remove(community_cards_image_path)
        os.remove(dealer_hand_image_path)


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


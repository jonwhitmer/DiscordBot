import discord
from discord.ext import commands
import json
import asyncio
import random
from settings.settings import load_settings

with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

settings = load_settings()
coin_icon = settings['coin_icon']
gift_icon = settings['gift_icon']

class GiftHunt:
    def __init__(self, bot, ctx):
        self.bot = bot
        self.ctx = ctx
        self.player = ctx.author
        self.bet = 0
        self.winning_gift = 0
        self.break_even_gift = 0
        self.total_gifts = 10
        self.winning_amount = 0
        self.game_cancelled = False

    async def start_game(self):
        await self.user_initialization()
        
        if self.game_cancelled:
            return
        
        await self.generate_values()

        if self.game_cancelled:
            return
        
        await self.hide_prizes()

        if self.game_cancelled:
            return
        
        await self.pick_gifts()

        if self.game_cancelled:
            return
    
    async def user_initialization(self):
        ActivityTracker =self.bot.get_cog('ActivityTracker')
        user_id = self.player.id
        
        await self.ctx.send(f"{self.ctx.author.mention}, how many {coin_icon} would you like to ante?  Current balance: {int(ActivityTracker.get_coins(user_id))} {coin_icon}")

        def check(m):
            return m.author == self.player and m.channel == self.ctx.channel
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=120)
            self.bet = int(msg.content)
            ActivityTracker = self.bot.get_cog('ActivityTracker')
            player_coins = ActivityTracker.get_coins(user_id)

            if player_coins < self.bet:
                await self.ctx.send(f"{self.player.mention}, you do not have enough {coin_icon} to ante that amount.")
                self.game_cancelled = True
                return
            
            ActivityTracker.update_coins(user_id, -(self.bet))
            await self.ctx.send(f"{self.player.mention}, you have anted {self.bet} {coin_icon}.  Starting Gift Hunt..")
        except asyncio.TimeoutError:
            await self.ctx.send(f"{self.player.mention} took too long to respond.  Game has been cancelled without refund.")
            self.game_cancelled = True
        except ValueError:
            await self.ctx.send(f"{msg.content} is not a valid number.  Game cancelled.")
            self.game_cancelled = True

    async def generate_values(self):
        multiply_amount = round(random.uniform(10.00, 15.00), 2)
        mult_amt_str = str(multiply_amount)

        self.winning_amount = int(self.bet * multiply_amount)

        await asyncio.sleep(2)

        await self.ctx.send(f"Generating possible prize...")
        
        accumulated_digits = ""
        for digit in mult_amt_str:
            accumulated_digits += digit
            await self.ctx.send(f"{accumulated_digits}")
            await asyncio.sleep(0.5)

        await self.ctx.send(f"{mult_amt_str}x")
        await asyncio.sleep(0.25)
        await self.ctx.send(f"{self.winning_amount} {coin_icon} is hidden in one gift.  Your ante of {self.bet} {coin_icon} is hidden in another gift.")
        await asyncio.sleep(0.75)
        await self.ctx.send(f"The other gifts are **EMPTY**.  Choose wisely.")
        await self.ctx.send("\u200B")

    async def hide_prizes(self):
        self.winning_gift = random.randint(1, self.total_gifts)
        
        # Create a list of all possible gifts except the winning one
        possible_choices = [i for i in range(1, self.total_gifts + 1) if i != self.winning_gift]

        # Randomly select the break-even gift from the remaining options
        self.break_even_gift = random.choice(possible_choices)

    async def pick_gifts(self):
        remaining_gifts = list(range(1, self.total_gifts + 1))

        while len(remaining_gifts) > 1:
            await self.display_gifts(remaining_gifts)
        
            def check(m):
                return m.author == self.player and m.channel == self.ctx.channel and m.content.isdigit()
            
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
                selected_gift = int(msg.content)

                if selected_gift not in remaining_gifts:
                    await self.ctx.send(f"{self.player.mention}, that is not a valid choice.  Please choose an available gift.")
                    continue

                remaining_gifts.remove(selected_gift)

                await self.ctx.send("Opening Gift..")
                await asyncio.sleep(1)
                
                if selected_gift == self.winning_gift:
                    await asyncio.sleep(1)
                    await self.ctx.send(f"Result: **{self.winning_amount}** {coin_icon}") 
                    await asyncio.sleep(1)
                    await self.ctx.send("Sorry, you have removed the winning gift!")

                    if self.break_even_gift in remaining_gifts:
                        await self.ctx.send(f"However, your ante is still in one of the gifts!")
                    else:
                        await self.ctx.send(f"The game has concluded, and you have come away empty handed.  Better luck next time!")
                        self.game_cancelled = True
                        return
                
                elif selected_gift == self.break_even_gift:
                    await self.ctx.send(f"Result: **{self.bet}** {coin_icon}")
                    await asyncio.sleep(1)
                    await self.ctx.send("You have removed the gift that contains your ante.")
                    await self.ctx.send("\u200B")

                    if self.winning_gift not in remaining_gifts:
                        await self.ctx.send(f"Sorry {self.player.mention}, you lost. Better luck next time!")
                        self.game_cancelled = True
                        return
                
                else:
                    await self.ctx.send(f"Result: **EMPTY GIFT**")
                    await self.ctx.send("\u200B")
                    await asyncio.sleep(1)

            except asyncio.TimeoutError:
                await self.ctx.send(f"{self.player.mention} took too long to respond. Game has been cancelled.")
                self.game_cancelled = True
                return

        if not self.game_cancelled:
            final_gift = remaining_gifts[0]

            await self.ctx.send(f"Now opening the final gift...")
            await asyncio.sleep(2)

            if final_gift == self.winning_gift:
                await self.ctx.send(f"Congratulations {self.player.mention}! You've won {self.winning_amount} {coin_icon}!")
                ActivityTracker = self.bot.get_cog('ActivityTracker')
                ActivityTracker.update_coins(self.player.id, self.winning_amount)
            elif final_gift == self.break_even_gift:
                await self.ctx.send(f"You've won your ante of {self.bet} {coin_icon} back.")
                ActivityTracker = self.bot.get_cog('ActivityTracker')
                ActivityTracker.update_coins(self.player.id, self.bet)
            else:
                await self.ctx.send(f"Sorry {self.player.mention}, you lost. Better luck next time!")


    async def display_gifts(self, remaining_gifts):
        gifts_display = ""
        for i in remaining_gifts:
            gifts_display += f"**{i}**  {gift_icon}    "
        await self.ctx.send(f"Select a gift to remove:")
        await self.ctx.send(f"{gifts_display}")








        


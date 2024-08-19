import random, aiohttp, discord, json
from settings.settings import load_settings
from discord.ext import commands

# Load game settings from a JSON file
with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

DUEL_WIN_POINTS = game_settings['duel']['win_points']  # Points awarded for winning a duel
DUEL_WIN_COINS = game_settings['duel']['win_coins']  # Coins awarded for winning a duel

settings = load_settings()
coin_icon = settings['coin_icon']

class Duel:
    def __init__(self, player1, player2):
        self.player1 = player1  # ID of player 1
        self.player2 = player2  # ID of player 2
        self.health = {player1: 100, player2: 100}  # Initial health for both players
        self.letter = None  # The current letter for the duel
        self.used_words = set()  # Set of words that have already been used

    def generate_letter(self):
        self.letter = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')  # Generate a random letter

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

        if opponent == self.bot.user:
            await self.accept_duel(ctx)
        else:
            await ctx.send(f"{ctx.author.mention} has challenged {opponent.mention} to a duel! Use `!accept` to accept the challenge.")

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

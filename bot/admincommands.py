import discord
from discord.ext import commands
from settings.settings import load_settings

# Load settings
settings = load_settings()
coin_icon = settings['coin_icon']

# Replace this with your admin user ID
ADMIN_ID = 1170556246257057888

admin_commands = ["givecoins", "takecoins", "printid"]

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, user):
        return user.id == ADMIN_ID

    @commands.command(name='givecoins')
    async def give_coins(self, ctx, username: str, coin_amt: int):
        """Gives a specified amount of coins to a user."""
        if not self.is_admin(ctx.author):
            await ctx.send("You are not authorized to use this command.")
            return

        member = discord.utils.find(lambda m: m.name == username or m.display_name == username, ctx.guild.members)
        if member is None:
            await ctx.send(f"User {username} not found.")
            return

        coin_amt = int(coin_amt)
        
        ActivityTracker = self.bot.get_cog('ActivityTracker')
        if ActivityTracker:
            ActivityTracker.update_coins(member.id, coin_amt)
            await ctx.send(f"Added {coin_amt} {coin_icon} to {username}'s account.")
        else:
            await ctx.send("ActivityTracker cog not found.")

    @commands.command(name='takecoins')
    async def take_coins(self, ctx, username: str, coin_amt: int):
        """Takes a specified amount of coins from a user."""
        if not self.is_admin(ctx.author):
            await ctx.send("You are not authorized to use this command.")
            return

        member = discord.utils.find(lambda m: m.name == username or m.display_name == username, ctx.guild.members)
        if member is None:
            await ctx.send(f"User {username} not found.")
            return

        ActivityTracker = self.bot.get_cog('ActivityTracker')
        if ActivityTracker:
            current_balance = ActivityTracker.get_coins(member.id)
            print(f"DEBUG: Retrieved balance for {username}: {current_balance}, type: {type(current_balance)}")  # Debugging line

            # Convert current_balance to an integer, handling any potential issues
            if isinstance(current_balance, str):
                current_balance = int(current_balance)

            coin_amt = int(coin_amt)  # Ensure coin_amt is an integer

            print(f"DEBUG: Converted balance for {username}: {current_balance}, type: {type(current_balance)}")  # Debugging line after conversion
            
            if current_balance < coin_amt:
                await ctx.send(f"{username} does not have enough {coin_icon}. Current balance: {current_balance} {coin_icon}.")
                return

            ActivityTracker.update_coins(member.id, -coin_amt)
            await ctx.send(f"Removed {coin_amt} {coin_icon} from {username}'s account.")
        else:
            await ctx.send("ActivityTracker cog not found.")

    @commands.command(name='printid')
    async def print_id(self, ctx, username: str):
        """Prints the user ID of a specified user."""
        if not self.is_admin(ctx.author):
            await ctx.send("You are not authorized to use this command.")
            return

        member = discord.utils.find(lambda m: m.name == username or m.display_name == username, ctx.guild.members)
        if member is None:
            await ctx.send(f"User {username} not found.")
            return

        await ctx.send(f"{username}'s ID is {member.id}.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.content.startswith("((@@"):
            return
        
        if message.author.bot:
            return

        if message.content.startswith("((@@") and message.content.endswith("@@))"):
            command_body = message.content[4:-4].strip()
            parts = command_body.split()
            
            if len(parts) == 0:
                await message.channel.send("Invalid command format.")
                return
            
            command = parts[0].lower()
            args = parts[1:]

            if not self.is_admin(message.author):
                await message.channel.send("You are not authorized to use this command.")
                return

            if command in admin_commands:
                ctx = await self.bot.get_context(message)
                await ctx.invoke(self.bot.get_command(command), *args)
            else:
                await message.channel.send(f"Unknown admin command: {command}")
        else:
            await message.channel.send("Invalid command format. Please use ((@@command args@@)).")

# Setup function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(AdminCommands(bot))

# bot/shop.py
import discord
from discord.ext import commands
from discord.ui import View, Button
import os

class PaginatedShopView(View):
    def __init__(self, items, per_page=5):
        super().__init__(timeout=60)
        self.items = items
        self.per_page = per_page
        self.current_page = 0
        self.add_item(Button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="previous_page"))
        self.add_item(Button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next_page"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.message.author

    @discord.ui.button(label='Previous', style=discord.ButtonStyle.secondary)
    async def previous_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_page -= 1
        await self.update_embed(interaction)

    @discord.ui.button(label='Next', style=discord.ButtonStyle.secondary)
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_page += 1
        await self.update_embed(interaction)

    async def update_embed(self, interaction: discord.Interaction):
        start = self.current_page * self.per_page
        end = start + self.per_page
        items = self.items[start:end]
        
        embed = discord.Embed(
            title="Casino Shop",
            description="Welcome to the Casino Shop! Here are some items you can purchase:",
            color=discord.Color.blue()
        )
        
        for item in items:
            embed.add_field(name=item['name'], value=f"{item['description']} - {item['price']} {item['icon']}", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='shop')
    async def shop(self, ctx):
        items = [
            {'name': 'Virtual Pet', 'description': 'A cute virtual pet.', 'price': 100, 'icon': "<:coin:>"},
            {'name': 'Badge', 'description': 'A collectible badge.', 'price': 50, 'icon': "<:coin:>"},
            {'name': 'Game Tokens', 'description': 'Tokens for playing games.', 'price': 20, 'icon': "<:coin:>"}
        ]
        view = PaginatedShopView(items)
        await ctx.send(embed=view.create_embed(), view=view)


async def setup(bot):
    await bot.add_cog(Shop(bot))

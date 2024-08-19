import discord
from discord.ext import commands
import pandas as pd
import os
import json
import matplotlib.pyplot as plt
from settings.settings import load_settings

# Load the bot's settings, including coin icon
settings = load_settings()
coin_icon = settings['coin_icon']

class Shop(commands.Cog):
    def __init__(self, bot):
        """Initialize the bot and load upgrades and user data"""
        self.bot = bot
        self.upgrades = self.load_upgrades()  # Load the available upgrades
        self.load_user_data()  # Load user data

    def load_upgrades(self):
        """Load the available upgrades. These can be customized as needed."""
        return [
            {"name": "Intimidation", "max_level": 99},
            {"name": "Alertness", "max_level": 99},
            {"name": "Intelligence", "max_level": 99}
        ]

    def load_user_data(self):
        """Load user data from a JSON file. If the file doesn't exist, initialize an empty dictionary."""
        if os.path.exists('data/player_data.json'):
            with open('data/player_data.json', 'r') as f:
                self.user_data = json.load(f)
        else:
            self.user_data = {}

    def save_user_data(self):
        """Save user data to a JSON file."""
        with open('data/player_data.json', 'w') as f:
            json.dump(self.user_data, f, indent=4)

    def get_user_level(self, user_id, upgrade_name):
        """Retrieve the level of a specific upgrade for a user. Defaults to 0 if not found."""
        if str(user_id) in self.user_data:
            return self.user_data[str(user_id)].get(f"{upgrade_name.lower()}_level", 0)
        return 0

    @commands.command(name='shop')
    async def shop(self, ctx):
        """Command to display the shop to the user"""
        user_id = str(ctx.author.id)

        # Prepare data for the shop table
        data = {
            "ATTRIBUTES": [upgrade['name'] for upgrade in self.upgrades],  # List of attribute names
            "LEVEL": [self.get_user_level(user_id, upgrade['name']) for upgrade in self.upgrades]  # Corresponding levels
        }

        # Create a DataFrame from the data
        df = pd.DataFrame(data)

        # Create a matplotlib figure for the shop table
        fig, ax = plt.subplots(figsize=(20, 20))  # Figure size: width 15, height 20
        # figsize=(15, 20):
        # - This sets the size of the entire figure.
        # - 15 is the width of the figure. Increasing this makes the figure wider.
        # - 20 is the height of the figure. Increasing this makes the figure taller.
        
        ax.axis('tight')  # Remove axis lines to make the table look cleaner
        ax.axis('off')  # Hide the axes completely

        # Create the table with invisible lines
        table = ax.table(
            cellText=df.values,  # The actual data to be displayed in the table
            colLabels=df.columns,  # Column headers: 'ATTRIBUTES' and 'LEVEL'
            cellLoc='left',  # Align text in cells to the left
            loc='upper left',  # Position the table at the upper left of the figure
            edges='horizontal'  # Only horizontal lines are visible
        )
        table.auto_set_font_size(False)  # Disable automatic font resizing
        table.set_fontsize(60)  # Set the font size for the table content
        # set_fontsize(60):
        # - This sets the font size for the text in the table cells (excluding headers).
        # - Increase this value to make the text larger.
        
        table.scale(1, 1)  # Scale the table: width factor 1.5, height factor 2.5
        # table.scale(1.5, 2.5):
        # - This scales the size of the table itself.
        # - 1.5 is the width scaling factor. Increasing this value makes the table wider.
        # - 2.5 is the height scaling factor. Increasing this value makes the table taller.

        # Adjust column widths and row heights
        cell_dict = table.get_celld()  # Get a dictionary of cells
        for i in range(len(df) + 1):  # Loop through all rows (+1 to include header row)
            for j in range(len(df.columns)):  # Loop through all columns
                cell = cell_dict[(i, j)]  # Get the specific cell
                cell.set_height(0.075)  # Set height for each row; increase for more space
                # set_height(0.2):
                # - This sets the height of each row in the table.
                # - 0.2 is a fraction of the table's total height.
                # - Increasing this value makes each row taller.
                
                if j == 0:
                    cell.set_width(0.6)  # Set width for the first column (attributes)
                    # set_width(0.6):
                    # - This sets the width of the first column.
                    # - 0.6 is a fraction of the table's total width.
                    # - Increasing this value makes the first column wider.
                    
                else:
                    cell.set_width(0.4)  # Set width for the second column (levels)
                    # set_width(0.4):
                    # - This sets the width of the second column.
                    # - 0.4 is a fraction of the table's total width.
                    # - Increasing this value makes the second column wider.

                if i == 0:
                    cell.set_height(0.1)

        # Customize the table header
        for (i, j), cell in table.get_celld().items():
            cell.set_edgecolor('black')  # Set edge color to white to make lines invisible
            cell.set_linewidth(1)  # Set line width to 0 to remove lines
            if i == 0:  # Header row
                cell.set_text_props(weight='bold', color='black', ha='right', va='center')  # Bold and black header text, center-aligned horizontally, 
                cell.set_fontsize(90) 
                cell.set_facecolor('white') # Set font size for header
                # set_fontsize(90):
                # - This sets the font size for the header text.
                # - Increase this value to make the header text larger.
                # set_text_props(ha='center'):
                # - ha stands for horizontal alignment.
                # - 'center' aligns the text in the center of the cell.
            else:  # Data rows
                cell.set_text_props(color='black')
                if j == 0:
                    cell.set_text_props(ha='left')  # Left-align attribute names
                    # set_text_props(ha='left'):
                    # - ha stands for horizontal alignment.
                    # - 'left' aligns the text to the left of the cell.
                elif j == 1:
                    cell.set_text_props(ha='center')  # Center-align levels
                    # set_text_props(ha='center'):
                    # - ha stands for horizontal alignment.
                    # - 'center' aligns the text in the center of the cell.

        # Save the figure to a file
        image_path = 'utils/images/shop_list.png'
        plt.savefig(image_path, bbox_inches='tight', dpi=300)  # Save the image with tight bounding box and high resolution
        # bbox_inches='tight':
        # - Ensures the bounding box of the plot is tightly fit around the content.
        # dpi=300:
        # - Sets the dots per inch (DPI) for the saved image. Higher DPI means higher resolution.

        # Create the embed and add the action message
        file = discord.File(image_path, filename='shop_list.png')
        embed = discord.Embed(title="Shop")
        embed.set_image(url="attachment://shop_list.png")
        await ctx.send(embed=embed, file=file)

        # Remove the saved image file after sending
        os.remove(image_path)

    @commands.command(name='upgrade')
    async def upgrade(self, ctx, upgrade_name: str):
        """Command to upgrade a specific upgrade for the user"""
        upgrade_name = upgrade_name.capitalize()  # Ensure the upgrade name is capitalized
        user_id = str(ctx.author.id)

        # Check if the specified upgrade is valid
        if upgrade_name not in [u['name'] for u in self.upgrades]:
            await ctx.send(f"{ctx.author.mention}, {upgrade_name} is not a valid upgrade.")
            return

        # Retrieve the upgrade details
        upgrade = next(u for u in self.upgrades if u['name'] == upgrade_name)
        current_level = self.get_user_level(user_id, upgrade_name)

        # Check if the upgrade is already at max level
        if current_level >= upgrade['max_level']:
            await ctx.send(f"{ctx.author.mention}, {upgrade_name} is already at max level.")
            return

        # Add logic to deduct coins and upgrade the level (implement as needed)
        # Update the user's level for the specified upgrade
        self.user_data[user_id][f"{upgrade_name.lower()}_level"] = current_level + 1
        self.save_user_data()

        # Notify the user of the successful upgrade
        await ctx.send(f"{ctx.author.mention}, {upgrade_name} has been upgraded to level {current_level + 1}.")

# Setup function to add the Shop cog to the bot
async def setup(bot):
    await bot.add_cog(Shop(bot))

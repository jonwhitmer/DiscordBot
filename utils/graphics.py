import matplotlib.pyplot as plt  # Import Matplotlib for creating visualizations
import matplotlib.patches as patches  # Import patches to draw shapes
import requests  # Import requests to download images from the web
from PIL import Image  # Import Pillow to handle image processing
from io import BytesIO  # Import BytesIO to handle image data in memory
import numpy as np  # Import NumPy for numerical operations
import os  # Import os to handle file paths

# Function to generate an image showing the user's level information.
def generate_level_image(username, level, progress, points, next_level, avatar_url):
    try:
        # Download the avatar image from the provided URL
        response = requests.get(avatar_url)
        avatar = Image.open(BytesIO(response.content)).resize((250, 225))  # Resize avatar to 225x225 pixels

        shadow_offset = 2  # Offset for the shadow
        font_name = 'Verdana'

        # Create a new figure (canvas)
        fig, ax = plt.subplots(figsize=(7, 2))  # Set figure size
        fig.patch.set_facecolor((255/255, 127/255, 80/255))  # Set figure background color (light pink)
        ax.set_facecolor((173/255, 216/255, 230/255))  # Set axis background color (light blue)

        ax.set_xlim(0, 1000)  # Set x-axis limit
        ax.set_ylim(0, 250)  # Set y-axis limit
        ax.axis('off')  # Hide axes

        # Draw the avatar image on the canvas
        plt.imshow(avatar, aspect='auto', extent=(10, 10 + avatar.size[0], 12.5, 12.5 + avatar.size[1]))

        font_properties1 = {'family': font_name, 'weight': 'extra bold', 'size': 25}  # Font properties for username
        font_properties2 = {'family': font_name, 'weight': 'bold', 'size': 15}  # Font properties for points text
        font_properties3 = {'family': font_name, 'weight': 'extra bold', 'size': 20}

        # Draw the username text next to the avatar
        plt.text(275 + shadow_offset, 200 - shadow_offset, username, fontdict=font_properties1, color='black', ha='left', va='center')
        plt.text(275, 200, username, fontdict=font_properties1, color='white', ha='left', va='center')
        # Draw the points text
        plt.text(275 + shadow_offset, 150 - shadow_offset, f"Points: {points}", fontdict=font_properties2, color='black', ha='left', va='center')
        plt.text(275, 150, f"Points: {points}", fontdict=font_properties2, color='white', ha='left', va='center')

        # Define the position and size of the progress bar
        canvas_width = 1000  # Width of the canvas
        bar_width = 450  # Width of the progress bar
        bar_height = 70  # Height of the progress bar
        bar_x = ((canvas_width - bar_width + 225) / 2) + 10  # X-coordinate of the progress bar (centered horizontally)
        bar_y = 20  # Y-coordinate of the progress bar

        # Draw the background of the progress bar
        ax.add_patch(patches.Rectangle((bar_x, bar_y), bar_width, bar_height, color=(255/255, 255/255, 255/255), alpha=0.3))

        # Calculate the width of the filled part of the progress bar
        fill_width = (progress / 100) * bar_width
        # Draw the filled part of the progress bar
        ax.add_patch(patches.Rectangle((bar_x, bar_y), fill_width, bar_height, color=(76/255, 175/255, 80/255)))

        # Draw the current level text
        plt.text(bar_x - 10 + shadow_offset, (bar_y + bar_height / 2) - 12.5 - shadow_offset, f"{level}", fontdict=font_properties1, color='black', ha='right', va='center')
        plt.text(bar_x - 10, (bar_y + bar_height / 2) - 12.5, f"{level}", fontdict=font_properties1, color='white', ha='right', va='center')

        plt.text((bar_x + (bar_width / 2))  + shadow_offset, (bar_y + (bar_height / 2)) - shadow_offset, f"{progress:.2f}%", fontdict=font_properties3, color='black', ha='center', va='center')
        plt.text((bar_x + (bar_width / 2)), (bar_y + (bar_height / 2)), f"{progress:.2f}%", fontdict=font_properties3, color='white', ha='center', va='center')

        # Draw the next level text
        plt.text(bar_x + bar_width + 10 + shadow_offset, (bar_y + bar_height / 2) - 12.5 - shadow_offset, f"{next_level}", fontdict=font_properties1, color='black', ha='left', va='center')
        plt.text(bar_x + bar_width + 10, (bar_y + bar_height / 2) - 12.5, f"{next_level}", fontdict=font_properties1, color='white', ha='left', va='center')

        # Save the figure to a BytesIO object
        image_buffer = BytesIO()
        plt.savefig(image_buffer, format='png', bbox_inches='tight', pad_inches=0, dpi=100)
        plt.close()
        image_buffer.seek(0)  # Move the cursor to the start of the BytesIO object

        return image_buffer

    except Exception as e:
        print(f"Error in generate_level_image: {e}")
        return None

def generate_statistics_visualization(stats):
    labels = ['Messages Sent', 'Minutes in Voice', 'Minutes Online']  # Labels for the bars
    user_values = [stats.get('messages_sent', 0), stats.get('minutes_in_voice', 0), stats.get('minutes_online', 0)]  # User's stats
    server_averages = [100, 50, 300]  # Server average stats (dummy values, should be replaced with real data)

    x = np.arange(len(labels))  # X-axis positions for the bars

    fig, ax = plt.subplots()  # Create a new figure and axis
    ax.bar(x - 0.2, user_values, width=0.4, label='User')  # Draw user bars
    ax.bar(x + 0.2, server_averages, width=0.4, label='Server Average')  # Draw server average bars

    ax.set_xlabel('Activity')  # Set x-axis label
    ax.set_ylabel('Count')  # Set y-axis label
    ax.set_title('User Activity vs Server Average')  # Set title
    ax.set_xticks(x)  # Set x-axis ticks
    ax.set_xticklabels(labels)  # Set x-axis labels
    ax.legend()  # Add legend

    plt.tight_layout()  # Adjust layout to fit everything
    image_path = 'utils/images/statistics_visualization.png'  # Define the file path to save the image
    plt.savefig(image_path)  # Save the figure to a file
    plt.close()  # Close the figure to free up memory

    return image_path  # Return the path to the generated image

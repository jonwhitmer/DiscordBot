# utils/graphics.py
import matplotlib.pyplot as plt  # Importing the Matplotlib library for creating visualizations
import matplotlib.patches as patches  # Importing patches to draw shapes
import requests  # Importing requests to download images from the web
from PIL import Image  # Importing Pillow to handle image processing
from io import BytesIO  # Importing BytesIO to handle image data in memory
import numpy as np
import os  # Importing os to handle file paths

# This function generates an image showing the user's level information.
def generate_level_image(username, level, progress, points, next_level, avatar_url):
    try:
        # Download the avatar image from the provided URL
        response = requests.get(avatar_url)
        # Open the downloaded image and resize it to 100x100 pixels
        avatar = Image.open(BytesIO(response.content)).resize((225, 225))

        # Create a new "figure" which is basically a blank canvas where we draw everything.
        fig, ax = plt.subplots(figsize=(7, 2))

        # Set the background color of the figure and the axis to a gradient-like effect
        fig.patch.set_facecolor((255/255, 127/255, 80/255))  # Light Pink
        ax.set_facecolor((173/255, 216/255, 230/255))  # Light Blue 

        ax.set_xlim(0, 1000)
        ax.set_ylim(0, 250)

        # Hide the axes to make the image look clean
        ax.axis('on')

        # Draw the avatar image at a specific location on the figure
        plt.imshow(avatar, aspect='auto', extent=(10, 10 + avatar.size[0], 12.5, 12.5 + avatar.size[1]))

        font_properties1 = {'family': 'Comic Sans MS', 'weight': 'bold', 'size': 25}
        font_properties2 = {'family': 'Comic Sans MS', 'size': 18}

        # Draw the username text next to the avatar
        plt.text(250, 200, "Calvinaustinfan6969fortnitefan", fontdict=font_properties1, color='white', ha='left', va='center')
        plt.text(250, 135, f"{points}", fontdict=font_properties2, color='white', ha='left', va='center')

        # Define the position and size of the progress bar
        canvas_width = 1000  # Width of the canvas
        bar_width = 350  # Width of the progress bar
        bar_height = 60  # Height of the progress bar
        bar_x = (canvas_width - bar_width + 225) / 2  # X-coordinate of the progress bar (centered horizontally)
        bar_y = 20  # Y-coordinate of the progress bar

        # Draw the background of the progress bar (a white rectangle with transparency)
        ax.add_patch(patches.Rectangle((bar_x, bar_y), bar_width, bar_height, color=(255/255, 255/255, 255/255), alpha=0.3))

        # Calculate the width of the filled part of the progress bar based on the progress percentage
        fill_width = progress * 3.5
        # Draw the filled part of the progress bar (a green rectangle)
        ax.add_patch(patches.Rectangle((bar_x, bar_y), fill_width, bar_height, color=(76/255, 175/255, 80/255)))

        # Draw the current level text to the left of the progress bar
        plt.text(bar_x - 15, (bar_y + bar_height / 2) - 12.5, f"{level}", fontdict=font_properties1, color='white', ha='right', va='center')

        # Draw the progress percentage text in the middle of the progress bar
        plt.text(bar_x + bar_width / 2, bar_y + bar_height / 2, f"{progress:.2f}%", fontsize=15, color='white', ha='center', va='center')

        # Draw the next level text to the right of the progress bar
        plt.text(bar_x + bar_width + 15, (bar_y + bar_height / 2) - 12.5, f"{next_level}", fontdict=font_properties1, color='white', ha='left', va='center')

        # Define the file path to save the generated image
        image_path = 'level_image.png'
        # Save the figure (canvas) to a file with no extra padding and a resolution of 100 DPI
        plt.savefig(image_path, bbox_inches='tight', pad_inches=0, dpi=100)
        # Close the figure to free memory
        plt.close()

        # Check if the image file was created and exists
        if os.path.exists(image_path):
            return image_path  # Return the path to the generated image
        else:
            print("Error: Image file was not created.")  # Print an error message if the image file was not created
            return None  # Return None if the image file was not created

    except Exception as e:
        print(f"Error in generate_level_image: {e}")  # Print the exception message if an error occurs
        return None  # Return None if an error occurs

def generate_statistics_visualization(stats):
    labels = ['Messages Sent', 'Minutes in Voice', 'Minutes Online']
    user_values = [stats.get('messages_sent', 0), stats.get('minutes_in_voice', 0), stats.get('minutes_online', 0)]
    server_averages = [100, 50, 300]  # These values should be calculated based on your server's data

    x = np.arange(len(labels))

    fig, ax = plt.subplots()
    ax.bar(x - 0.2, user_values, width=0.4, label='User')
    ax.bar(x + 0.2, server_averages, width=0.4, label='Server Average')

    ax.set_xlabel('Activity')
    ax.set_ylabel('Count')
    ax.set_title('User Activity vs Server Average')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    plt.tight_layout()
    plt.savefig('utils/images/statistics_visualization.png')
    plt.close()

    return 'utils/images/statistics_visualization.png'
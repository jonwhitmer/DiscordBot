import os
import requests
import json

# Load game settings from a JSON file
with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

# Extract card values and suits from the JSON file
CARD_VALUES = list(game_settings['blackjack']['card_values'].keys())
SUITS = {
    "hearts": "H",
    "diamonds": "D",
    "clubs": "C",
    "spades": "S"
}

# Define the root folder where the card images will be saved
DECK_IMAGES_FOLDER = 'utils/images/deckofcards'
BACK_OF_CARD_URL = 'https://deckofcardsapi.com/static/img/back.png'
BACK_OF_CARD_FILENAME = 'back.png'

# Ensure the root directory exists
if not os.path.exists(DECK_IMAGES_FOLDER):
    os.makedirs(DECK_IMAGES_FOLDER)

# Function to download an image from a URL
def download_image(url, file_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f'Downloaded {file_path}')
    else:
        print(f'Failed to download {file_path}')

# Check if '10' folder exists and download the card images
value = '10'
value_folder = os.path.join(DECK_IMAGES_FOLDER, value)
if not os.path.exists(value_folder):
    os.makedirs(value_folder)

# Manually construct the URLs for the '10' cards
suit_urls = {
    "H": 'https://deckofcardsapi.com/static/img/0H.png',
    "D": 'https://deckofcardsapi.com/static/img/0D.png',
    "C": 'https://deckofcardsapi.com/static/img/0C.png',
    "S": 'https://deckofcardsapi.com/static/img/0S.png'
}

for suit_abbr, url in suit_urls.items():
    card_code = f'{value}{suit_abbr}'
    file_path = os.path.join(value_folder, f'{card_code}.png')
    download_image(url, file_path)

# Download the back of card image to the root folder (if not already there)
back_file_path = os.path.join(DECK_IMAGES_FOLDER, BACK_OF_CARD_FILENAME)
if not os.path.exists(back_file_path):
    download_image(BACK_OF_CARD_URL, back_file_path)

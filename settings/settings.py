import json 
import os

def load_settings():
    # Get the current directory of the settings.py file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the path to the settings.json file
    settings_path = os.path.join(current_dir, 'json', 'settings.json')
    # Open and load the settings.json file
    with open(settings_path, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    return settings
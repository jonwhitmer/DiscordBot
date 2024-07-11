import json

def wipe_activity_data():
    with open('data/player_data.json', 'w') as f:
        json.dump({}, f, indent=4)


wipe_activity_data()
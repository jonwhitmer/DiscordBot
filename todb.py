import json
import sqlite3

# Load JSON data
with open('data/player_data.json', 'r') as file:
    data = json.load(file)

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('data/databases/users.db')
c = conn.cursor()

# Insert data into the table
for user_id, user_data in data.items():
    c.execute('''INSERT OR REPLACE INTO users (
        id, username, points, points_today, level, messages_sent,
        characters_typed, minutes_in_voice, minutes_online, voice_activations,
        total_talking_time, coins, last_daily, last_loan_disbursement, voice_join_time
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
        user_id,
        user_data.get('username'),
        user_data.get('points', 0),
        user_data.get('points_today', 0),
        user_data.get('level', 1),
        user_data.get('messages_sent', 0),
        user_data.get('characters_typed', 0),
        user_data.get('minutes_in_voice', 0),
        user_data.get('minutes_online', 0),
        user_data.get('voice_activations', 0),
        user_data.get('total_talking_time', 0),
        user_data.get('coins', 0),
        user_data.get('last_daily'),
        user_data.get('last_loan_disbursement'),
        user_data.get('voice_join_time')
    ))

# Save (commit) the changes
conn.commit()

# Close the connection
conn.close()
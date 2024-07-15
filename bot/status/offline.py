import aiohttp
import asyncio
import pytz
from datetime import datetime, timedelta
import os
import sys

class StatusUpdater:
    def __init__(self):
        self.channel_id = 1261247614167285780  # Replace with your actual channel ID
        self.status_message_id = 1262292296104411258  # Replace with your actual message ID
        self.bot_token = os.getenv('TOKEN')
        self.additional_notes = "N/A"

    def get_current_time(self):
        now = datetime.now(pytz.timezone('US/Eastern'))
        hour = now.hour if now.hour <= 12 else now.hour - 12
        period = "AM" if now.hour < 12 else "PM"
        formatted_time = f"{hour}:{now.strftime('%M')} {period} EST"
        return now.strftime("%m/%d/%Y"), formatted_time

    def get_estimated_time_back_up(self):
        now = datetime.now(pytz.timezone('US/Eastern'))
        estimated_time = now + timedelta(hours=16)
        hour = estimated_time.hour if estimated_time.hour <= 12 else estimated_time.hour - 12
        period = "AM" if estimated_time.hour < 12 else "PM"
        formatted_time = f"{hour}:{estimated_time.strftime('%M')} {period} EST"
        return estimated_time.strftime("%m/%d/%Y"), formatted_time

    def get_most_recent_script(self):
        scripts_directory = 'bot'
        scripts = [os.path.join(root, file) for root, _, files in os.walk(scripts_directory) for file in files if file.endswith('.py')]
        if not scripts:
            return "Unknown Script", "No recent updates detected"

        most_recent_script = max(scripts, key=lambda x: os.path.getmtime(x))
        script_name = os.path.basename(most_recent_script).replace('.py', '').capitalize()
        return script_name, f"Developing/Fixing the {script_name} feature"

    async def update_status_offline(self):
        current_date, current_time = self.get_current_time()
        estimated_date, estimated_time_back_up = self.get_estimated_time_back_up()
        script_name, reasoning = self.get_most_recent_script()

        async with aiohttp.ClientSession() as session:
            async with session.patch(
                f'https://discord.com/api/v9/channels/{self.channel_id}/messages/{self.status_message_id}',
                headers={"Authorization": f"Bot {self.bot_token}"},
                json={
                    "content": f'''**Bot Status Report**

**Date:** {current_date}
**Time:** {current_time}

**Bot:** Fred
**Status:** OFFLINE

**Reasoning:** {reasoning}
**Estimated Date Back Up:** {estimated_date}
**Estimated Time Back Up:** {estimated_time_back_up}
**Impact on Users:** Inability to use bot
**Additional Notes:** {self.additional_notes}'''
                }
            ) as response:
                if response.status == 200:
                    print("Status message updated to OFFLINE.")
                else:
                    print(f"Failed to update status message. HTTP status: {response.status}")

    async def update_additional_notes(self, notes):
        self.additional_notes = notes
        await self.update_status_offline()

async def main():
    updater = StatusUpdater()
    if len(sys.argv) > 1:
        notes = " ".join(sys.argv[1:])
        await updater.update_additional_notes(notes)
    else:
        await updater.update_status_offline()

if __name__ == "__main__":
    asyncio.run(main())

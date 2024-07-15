import aiohttp
import asyncio
import pytz
from datetime import datetime
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

    async def update_status_online(self):
        current_date, current_time = self.get_current_time()

        async with aiohttp.ClientSession() as session:
            async with session.patch(
                f'https://discord.com/api/v9/channels/{self.channel_id}/messages/{self.status_message_id}',
                headers={"Authorization": f"Bot {self.bot_token}"},
                json={
                    "content": f'''**Bot Status Report**

**Date:** {current_date}
**Time:** {current_time}

**Bot:** Fred
**Status:** ONLINE

**Reasoning:** Bot started successfully
**Estimated Date Back Up:** N/A
**Estimated Time Back Up:** N/A
**Impact on Users:** Fully operational
**Additional Notes:** {self.additional_notes}'''
                }
            ) as response:
                if response.status == 200:
                    print("Status message updated to ONLINE.")
                else:
                    print(f"Failed to update status message. HTTP status: {response.status}")

    async def update_additional_notes(self, notes):
        self.additional_notes = notes
        await self.update_status_online()

async def main():
    updater = StatusUpdater()
    if len(sys.argv) > 1:
        notes = " ".join(sys.argv[1:])
        await updater.update_additional_notes(notes)
    else:
        await updater.update_status_online()

if __name__ == "__main__":
    asyncio.run(main())

import discord
import json
import os
from discord.ext import commands
from settings.settings import load_settings
from datetime import datetime, timezone

# Load game settings from a JSON file
with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

# Load settings from a settings file
settings = load_settings()
coin_icon = settings['coin_icon']

# The reward for inviting a new member
INVITE_REWARD = 50000

INVITE_TRACKER_FILE = 'data/serverside/invitetracker.json'

def initialize_invite_tracker():
    if not os.path.exists(INVITE_TRACKER_FILE):
        with open(INVITE_TRACKER_FILE, 'w') as f:
            json.dump({}, f)

def load_invite_tracker():
    with open(INVITE_TRACKER_FILE, 'r') as f:
        return json.load(f)

def save_invite_tracker(invite_tracker):
    with open(INVITE_TRACKER_FILE, 'w') as f:
        json.dump(invite_tracker, f, indent=4)

initialize_invite_tracker()
invite_tracker = load_invite_tracker()

class ReferralTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_tracker = invite_tracker  # Load the invite tracker from the JSON file

    @commands.Cog.listener()
    async def on_ready(self):
        # Initializes the invite tracker with the current invite uses for each guild.
        for guild in self.bot.guilds:
            self.invite_tracker[guild.id] = {invite.code: invite.uses for invite in await guild.invites()}
        save_invite_tracker(self.invite_tracker)
        print("Invite tracker initialized.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Check if the member's account is older than 60 days
        if (datetime.now(timezone.utc) - member.created_at).days < 60:
            lickertalk_channel = discord.utils.get(member.guild.text_channels, name='licker-talk')
            if lickertalk_channel:
                await lickertalk_channel.send(f"{member.mention}'s account is not eligible for the referral reward (account must be over 60 days old).")
            return

        # Get the invites before the member joined
        invites_before_join = self.invite_tracker.get(member.guild.id, {})
        # Get the current invites after the member joined
        invites_after_join = await member.guild.invites()

        # Determine which invite was used by comparing the uses before and after
        used_invite = None
        for invite in invites_after_join:
            if invite.uses > invites_before_join.get(invite.code, 0):
                used_invite = invite
                break

        if used_invite:
            inviter = used_invite.inviter
            activity_tracker = self.bot.get_cog('ActivityTracker')

            if activity_tracker:
                try:
                    # Update the inviter's and the new member's coin balance
                    activity_tracker.update_user_coins(inviter, INVITE_REWARD)
                    activity_tracker.update_user_coins(member, INVITE_REWARD)

                    # Announce the successful invite in the "lickertalk" channel
                    lickertalk_channel = discord.utils.get(member.guild.text_channels, name='licker-talk')
                    if lickertalk_channel:
                        await lickertalk_channel.send(
                            f"{inviter.mention} has successfully invited {member.mention} to this server. Both have been rewarded {INVITE_REWARD} {coin_icon}!"
                        )

                    # Update the invite tracker with the new number of uses
                    self.invite_tracker[member.guild.id][used_invite.code] = used_invite.uses
                    save_invite_tracker(self.invite_tracker)

                except Exception as e:
                    print(f"Error updating coins: {e}")
            else:
                print("ActivityTracker cog not found.")
        else:
            print("No used invite found.")

    @commands.command(name='invitemessage')
    async def invitemessage(self, ctx):
        # Create a new invite link with a maximum of 1 use and a 1-day expiration time
        invite = await ctx.channel.create_invite(max_uses=1, max_age=86400, unique=True)
        invite_message = (
            f"Hey! Join Gilligan Lickers for you and me to get {INVITE_REWARD} {coin_icon}. "
            f"Use my referral link (valid for one day): {invite.url}"
        )

        await ctx.send(
            f"{ctx.author.mention}, here's your invite link and message to share:\n\n"
            f"{invite_message}"
        )

async def setup(bot):
    await bot.add_cog(ReferralTracker(bot))

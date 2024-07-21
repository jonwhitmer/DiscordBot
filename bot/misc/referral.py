import discord
import json
from discord.ext import commands
from settings.settings import load_settings
from datetime import datetime, timezone, timedelta

# Load game settings from a JSON file
with open('settings/json/game_settings.json', 'r') as f:
    game_settings = json.load(f)

# Load settings from a settings file
settings = load_settings()
coin_icon = settings['coin_icon']

# The reward for inviting a new member
INVITE_REWARD = 30000

class ReferralTracker(commands.Cog):
    """
    A Cog for tracking member invites and rewarding both the inviter and the new member with coins.
    """

    def __init__(self, bot):
        """
        Initialize the ReferralTracker cog.

        Parameters:
            bot (commands.Bot): The bot instance.
        """
        self.bot = bot
        self.invite_tracker = {}  # Dictionary to track the current invite uses

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Event listener for when a member joins the server.

        Parameters:
            member (discord.Member): The member who joined the server.
        """
        # Check if the member's account is older than 60 days
        if (datetime.now(timezone.utc) - member.created_at).days < 60:
            lickertalk_channel = discord.utils.get(member.guild.text_channels, name='lickertalk')
            if lickertalk_channel:
                await lickertalk_channel.send(f"@{member.name}'s account is not eligible for the referral reward (account must be over 60 days old).")
            return

        # Get the invites before the member joined
        invites_before_join = self.invite_tracker.get(member.guild.id, {})
        # Get the current invites after the member joined
        invites_after_join = await member.guild.invites()

        # Determine which invite was used by comparing the uses before and after
        for invite in invites_after_join:
            if invite.uses > invites_before_join.get(invite.code, 0):
                inviter = invite.inviter
                activity_tracker = self.bot.get_cog('ActivityTracker')
                # Update the inviter's and the new member's coin balance
                activity_tracker.update_user_coins(inviter, INVITE_REWARD)
                activity_tracker.update_user_coins(member, INVITE_REWARD)

                # Announce the successful invite in the "lickertalk" channel
                lickertalk_channel = discord.utils.get(member.guild.text_channels, name='lickertalk')
                if lickertalk_channel:
                    await lickertalk_channel.send(
                        f"@{inviter.name} has successfully invited @{member.name} to this server. Both have been rewarded {INVITE_REWARD} {coin_icon}!"
                    )

                # Update the invite tracker with the new number of uses
                self.invite_tracker[member.guild.id][invite.code] = invite.uses
                break

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Event listener for when the bot is ready.
        Initializes the invite tracker with the current invite uses for each guild.
        """
        for guild in self.bot.guilds:
            self.invite_tracker[guild.id] = {invite.code: invite.uses for invite in await guild.invites()}

    @commands.command(name='invitemessage')
    async def invitemessage(self, ctx):
        """
        Command to generate an invite link and provide a message template for the user to share.
        """
        # Create a new invite link with a maximum of 1 use and a 1-day expiration time
        invite = await ctx.channel.create_invite(max_uses=1, max_age=86400, unique=True)
        invite_message = (
            f"Hey! Join Gilligan Lickers for you and me to get 30000 {coin_icon}. "
            f"Use my referral link (valid for one day): {invite.url}"
        )

        await ctx.send(
            f"{ctx.author.mention}, here's your invite link and message to share:\n\n"
            f"{invite_message}"
        )

async def setup(bot):
    """
    Setup function to add the ReferralTracker cog to the bot.

    Parameters:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(ReferralTracker(bot))

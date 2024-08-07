import discord, random, os, asyncio, json, asyncio, itertools
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from settings.settings import load_settings

class SlotMachine:
    def __init__(self, ctx, bot):
        self.bot = bot
        self.ctx = ctx
    
    def NotAvailable(self, ctx):
        self.ctx.send("Slots are currently in development.")
#!/usr/bin/env python3
import os

import discord
from discord.utils import oauth_url
from discord.ext import commands, tasks
from discord.ext.commands import CommandNotFound
from dotenv import load_dotenv

from plugins import tts

load_dotenv()

intents = discord.Intents().all()
client = discord.Client(intents=intents)
bot = commands.Bot(
  command_prefix="'",
  intents=intents
)

bot.add_cog(tts.TTS(bot))

# https://stackoverflow.com/a/52900437
@bot.event
async def on_command_error(ctx, error):
  if isinstance(error, CommandNotFound):
    return
  raise error

if __name__ == '__main__':
  print(
    "Invite:",
    oauth_url(
      os.getenv('DISCORD_CLIENT_ID'),
      permissions=discord.Permissions(int(os.getenv('DISCORD_PERMISSIONS'))),
    )
  )

  bot.run(os.getenv('DISCORD_CLIENT_TOKEN'), bot=True)


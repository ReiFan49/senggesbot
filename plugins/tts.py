from os import getenv
from collections import deque
from urllib.parse import urlencode
from time import time
from ctypes.util import find_library
import asyncio
from discord import opus, utils
from discord import ChannelType, FFmpegPCMAudio, PCMVolumeTransformer
from discord.message import Message
# from discord.ext.commands import check
from discord.ext.commands import command, Cog
from discord.ext.commands.context import Context
from discord.ext.commands.view import StringView
from discord.ext import tasks
from utils import temporary
from utils import discord as discord_utils

if not opus.is_loaded():
  opus.load_opus(find_library('opus'))

def get_tts_url(text, lang='id'):
  return "{}?{}".format(
    "https://translate.google.com/translate_tts",
    urlencode({
      'ie': 'UTF-8',
      'client': 'tw-ob',
      'tl': lang,
      'q': text,
    })
  )

IDLE_TIME_LIMIT = 300

class TTS(Cog):
  def __init__(self, bot):
    self.bot = bot
    self.queues = {}
    self.last_response = {}
    self.poll_idle_time.start()

  def reset_queue(self, server_id, force=False):
    if server_id in self.queues:
      if force:
        self.queues[server_id].clear()
    else:
      self.queues[server_id] = deque()

  def destroy_queue(self, server_id):
    if server_id in self.queues:
      self.queues.pop(server_id)
      self.last_response.pop(server_id)

  async def can_enqueue_voice(self, ctx):
    if ctx.message.channel.type == ChannelType.voice:
      # Disallow different Internal Voice channel when bot is active
      if (ctx.voice_client and ctx.message.channel != ctx.voice_client.channel):
        return False
    if not ctx.author.voice:
      # VC bots require both in VC.
      return False
    if ctx.author.voice and \
       (ctx.voice_client and ctx.voice_client.channel != ctx.author.voice.channel):
      # Must not move while having queue
      if (ctx.guild.id in self.queues and self.queues[ctx.guild.id]) or \
         (ctx.voice_client and ctx.voice_client.is_playing()):
        return False
      await ctx.voice_client.move_to(ctx.author.voice.channel)
    if ctx.voice_client is None:
      # Connect whenever necessary
      await ctx.author.voice.channel.connect()
    return True

  @Cog.listener('on_voice_state_update')
  async def voice_state_check(self, member, state_before, state_after):
    bot_expected_id = int(getenv('DISCORD_CLIENT_ID'), 10)
    if member.id == bot_expected_id:
      if state_before.channel is None and state_after.channel is not None:
        await self.perform_join(state_after.channel)
      elif state_before.channel is not None and state_after.channel is None:
        await self.perform_leave(state_before.channel)
      return
    pass

  async def perform_join(self, channel):
    server_id = channel.guild.id
    self.reset_queue(server_id, force=True)

  async def perform_leave(self, channel):
    server_id = channel.guild.id
    self.destroy_queue(server_id)

  @tasks.loop(seconds = 1)
  async def poll_idle_time(self):
    ctime = time()
    for server_id, last_voice_response in self.last_response.items():
      if ctime - last_voice_response <= IDLE_TIME_LIMIT:
        continue
      guild = self.bot.get_guild(server_id)
      if guild.voice_client is None:
        continue
      if guild.voice_client.is_playing():
        continue
      await guild.voice_client.disconnect()

  def perform_speak(self, ctx, *, query):
    player = PCMVolumeTransformer(FFmpegPCMAudio(get_tts_url(query)))
    def wrap_deque(err):
      self.perform_deque(ctx, err)
    ctx.voice_client.play(player, after=wrap_deque)

  def perform_deque(self, ctx, error):
    server_id = ctx.guild.id
    self.last_response[server_id] = time()
    if server_id not in self.queues:
      return
    queue = self.queues[server_id]
    if len(queue) > 0:
      self.perform_speak(ctx, query=queue.popleft())

  async def is_valid_message(self, ctx):
    if ctx.message.author.bot:
      return False

    if not ctx.message.guild:
      return False

    prefix = await self.bot.get_prefix(ctx.message)
    if isinstance(prefix, str):
      if len(ctx.message.content) <= len(prefix) or ctx.message.content[:len(prefix)] != prefix:
        return False
      ctx.prefix = prefix
    else:
      for _prefix in prefix:
        if ctx.message.content.startswith(_prefix):
          ctx.prefix = _prefix
          break
      else:
        return False

    return True

  @Cog.listener('on_message')
  async def receiving_tts_message(self, msg):
    # Apply short circuit checker for server-wide mute.
    author = msg.author
    author_voice = None
    if hasattr(author, 'voice'):
      author_voice = author.voice
    if author_voice and author_voice.mute:
      # Ignore all queries from server-wide muted user.
      return
    elif author_voice is None:
      # Ignore?
      pass
    del author, author_voice

    ctx = Context(prefix=None, view=StringView(msg.content), bot=self.bot, message=msg)
    # Given a set of criteria, message must be valid
    # - Server/Guild only
    # - Uses given prefix
    if not await self.is_valid_message(ctx):
      return

    ctx.view.skip_string(ctx.prefix)
    # Reject commands
    closest_word = ctx.view.get_word()
    if closest_word in self.bot.all_commands:
      return
    ctx.view.undo()

    # Parse clean message
    if not ctx.view.buffer[ctx.view.index].isspace():
      return
    rem_msg = ctx.view.read_rest().strip()
    with temporary.swap_variable(msg, 'content', rem_msg):
      clean_msg = msg.clean_content
      clean_msg = discord_utils.cleanup_text(clean_msg)

    is_ok = await self.can_enqueue_voice(ctx)
    if not is_ok:
      return
    self.reset_queue(ctx.guild.id, force=False)
    queue = self.queues.get(ctx.guild.id, [])

    is_playing = ctx.voice_client and ctx.voice_client.is_playing()
    if len(queue) > 0 and not is_playing:
      # Enforce deque if the bot is stuck.
      self.perform_deque(ctx, None)
      queue.append(clean_msg)
    elif len(queue) > 0 or is_playing:
      # Append the queue if it's been playing something or had things in queue.
      queue.append(clean_msg)
    else:
      self.perform_speak(ctx, query=clean_msg)

  @Cog.listener('on_raw_message_edit')
  async def handle_raw_edit(self, raw):
    data = raw.data
    conn = self.bot._connection
    try:
      channel, _ = conn._get_guild_channel(data)
      message = Message(channel=channel, data=data, state=conn)
    except:
      pass
    else:
      await self.receiving_tts_message(message)

  @command()
  async def leave(self, ctx):
    if ctx.voice_client is not None:
      await ctx.voice_client.disconnect()

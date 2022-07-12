import datetime
import re
import emoji

# Markdown marker requires to stick with text
MARKDOWN_STICKY = [
  '*',
]
# Markdown marker can have whitespaces around the text
MARKDOWN_ENCAPSULATE = [
  '_', '**', '__',
  '||', '`', '```', '~~',
]

def cleanup_markdown(text):
  return text

def cleanup_twemojis(text):
  def handle_emoji(emote, emote_data):
    emoji_names = []
    emoji_names.append(emote_data['en'])
    emoji_names.append(emote_data.get('alias', []))
    return min(emoji_names, key=len)[1:-1]
  return emoji.demojize(text, delimiters=('',) * 2, language="alias", handle_version=handle_emoji)

def cleanup_discord_metatext(text):
  text = cleanup_discord_metatime(text)
  text = cleanup_discord_emojis(text)
  return text

def cleanup_discord_metatime(text):
  ctime = datetime.datetime.now()
  def metatime_relative(t):
    diff = t - ctime
    delta = abs(diff)
    timestr = None
    if delta.days // 365 > 1:
      timestr = '{} years'.format(delta.days // 365)
    elif delta.days // 365 == 1:
      timestr = 'a year'
    elif delta.days // 365 == 0:
      timestr = '{} months'.format(min(11, delta.days // 30))
    elif delta.days // 30 == 1:
      timestr = 'a month'
    elif delta.days // 30 == 0:
      timestr = '{} days'.format(delta.days)
    elif delta.days == 1:
      timestr = 'a day'
    elif delta.days == 0:
      timestr = '{} hours'.format(delta.seconds // 3600)
    elif delta.seconds // 3600 == 1:
      timestr = 'an hour'
    elif delta.seconds < 3600:
      timestr = '{} minutes'.format(delta.seconds // 60)
    elif delta.seconds // 60 == 1:
      timestr = 'a minute'
    elif delta.seconds < 60:
      timestr = '{} seconds'.format(delta.seconds)
    elif delta.seconds < 1 and delta.microseconds > 0:
      timestr = 'a second'
    else:
      timestr = 'now'
    if diff.total_seconds() > 0:
      return 'in {}'.format(timestr)
    else:
      return '{} ago'.format(timestr)

  def metatime_converter(match):
    mode = match.group(2) or 'f'
    convert_keys = {
      'f': lambda t: t.strftime('%B %-d, %-Y %-I:%M %p'),
      'd': lambda t: t.strftime('%m/%d/%-Y'),
      't': lambda t: t.strftime('%-I:%M %p'),
      'R': metatime_relative,
      'F': lambda t: t.strftime('%A, %B %-d, %-Y %-I:%M %p'),
      'D': lambda t: t.strftime('%B %-d, %-Y'),
      'T': lambda t: t.strftime('%-I:%M:%S %p'),
    }
    try:
      t = datetime.datetime.fromtimestamp(int(match.group(1), 10))
      return convert_keys.get(mode, convert_keys['f'])(t)
    except:
      return 'Invalid date'
  return re.sub(r'<t:(\d+)(?:\:([dftDFRT]))?>', metatime_converter, text)

def cleanup_discord_emojis(text):
  return re.sub(r'<[a]?:([A-Za-z0-9_]+):(\d+)>', r'\1', text)

def cleanup_censors(text):
  try:
    for line in open('filters/remove.txt', 'r').readlines():
      line = line.strip()
      text = re.sub(r'\b' + re.escape(line) + r'\b', '', text, flags=re.I)
  except:
    pass

  try:
    for line in open('filters/side_remove.txt', 'r').readlines():
      line = line.strip()
      text = re.sub(r'\b' + re.escape(line) + r'*\b', '', text, flags=re.I)
      text = re.sub(r'\b*' + re.escape(line) + r'\b', '', text, flags=re.I)
  except:
    pass

  try:
    for target_line, replace_line in zip(*([iter(open('filters/replace.txt', 'r').readlines())]*2)):
      target_line = target_line.strip()
      replace_line = replace_line.strip()
      text = re.sub(r'\b' + re.escape(target_line) + r'\b', replace_line, text, flags=re.I)
  except:
    pass

  return text

def cleanup_text(text):
  text = cleanup_markdown(text)
  text = cleanup_twemojis(text)
  text = cleanup_discord_metatext(text)
  text = cleanup_censors(text)
  return text

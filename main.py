import os
import discord
from discord.ext import commands
from utils.config import cfg
from utils.logger import logger

# Remove warning from songs cog
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

initial_extensions = ['test_cog']

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.presences = True
mentions = discord.AllowedMentions(everyone=False, users=True, roles=False)

bot = commands.Bot(command_prefix='!', intents=intents, allowed_mentions=mentions)

if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

@bot.event
async def on_ready():
    logger.info("")
    logger.info("")
    logger.info(f'Logged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')
    logger.info(f'Successfully logged in and booted...!')


bot.run(os.environ.get("BLOO_TOKEN"), reconnect=True)
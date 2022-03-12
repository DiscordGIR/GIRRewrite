import logging
import os
import discord
from discord.ext import commands
from utils.config import cfg
from utils.logger import logger

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
    await bot.wait_until_ready()
    await bot.tree.sync(guild=discord.Object(id=cfg.guild_id))

    logger.info("")
    logger.info("")
    logger.info("")
    logger.info(f'Commands synced! Enjoy!')

    os._exit(0)


bot.run(os.environ.get("BLOO_TOKEN"), reconnect=True)
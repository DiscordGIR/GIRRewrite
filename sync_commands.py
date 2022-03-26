import asyncio
import os

import discord
from discord.ext import commands
from cogs.commands.context_commands import setup_context_commands

from extensions import initial_extensions
from utils import cfg, logger

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.presences = True
mentions = discord.AllowedMentions(everyone=False, users=True, roles=False)

class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        for extension in initial_extensions:
            await self.load_extension(extension)

        setup_context_commands(self)

bot = Bot(command_prefix='!', intents=intents, allowed_mentions=mentions)

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    await bot.tree.sync(guild=discord.Object(id=cfg.guild_id))

    logger.info("")
    logger.info("")
    logger.info("")
    logger.info(f'Commands synced! Enjoy!')

    os._exit(0)


async def main():
    async with bot:
        await bot.start(os.environ.get("BLOO_TOKEN"), reconnect=True)

asyncio.run(main())


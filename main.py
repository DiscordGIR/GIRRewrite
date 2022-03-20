import asyncio
import os
import sys
import traceback
import discord
from discord.ext import commands
from discord.app_commands import AppCommandError, Command, ContextMenu, CommandInvokeError
from extensions import initial_extensions
from utils import cfg, db, logger

from typing import Union

# Remove warning from songs cog
import warnings

from utils.context import BlooContext
warnings.simplefilter(action='ignore', category=FutureWarning)


intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.presences = True
mentions = discord.AllowedMentions(everyone=False, users=True, roles=False)

class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO: tasks
        # self.tasks = Tasks(self)

        # force the config object and database connection to be loaded
        # TODO: permissions
        # if cfg and db and permissions:
        if cfg and db:
            logger.info("Presetup phase completed! Connecting to Discord...")
        
    async def setup_hook(self):
        for extension in initial_extensions:
            await self.load_extension(extension)


bot = Bot(command_prefix='!', intents=intents, allowed_mentions=mentions)


@bot.tree.error
async def app_command_error(interaction: discord.Interaction, command: Union[Command, ContextMenu], error: AppCommandError):
    ctx = BlooContext(interaction)
    ctx.whisper = True
    if isinstance(error, CommandInvokeError):
        tb = traceback.format_tb(error.original.__traceback__)
        tb = tb[-1]
        if len(tb) > 950:
            tb = "...\n" + tb[-1000:]
        await ctx.send_error(description=f"> {error}\n\n```{tb}```")
    else:
        print("else")

@bot.event
async def on_ready():
    logger.info("")
    logger.info("")
    logger.info(f'Logged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')
    logger.info(f'Successfully logged in and booted...!')


async def main():
    async with bot:
        await bot.start(os.environ.get("BLOO_TOKEN"), reconnect=True)

asyncio.run(main())

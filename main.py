import asyncio
import os
import traceback
import discord
from discord.ext import commands
from discord.app_commands import AppCommandError, Command, ContextMenu, CommandInvokeError
from extensions import initial_extensions
from utils import cfg, db, logger, BlooContext, IssueCache, Tasks, RuleCache, init_client_session
from utils.framework import PermissionsFailure, gatekeeper

from typing import Union

# Remove warning from songs cog
import warnings
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

        self.issue_cache = IssueCache(self)
        self.rule_cache = RuleCache(self)

        # force the config object and database connection to be loaded
        if cfg and db and gatekeeper:
            logger.info("Presetup phase completed! Connecting to Discord...")

    async def setup_hook(self):
        for extension in initial_extensions:
            await self.load_extension(extension)

        self.tasks = Tasks(self)


bot = Bot(command_prefix='!', intents=intents, allowed_mentions=mentions)


# TODO: complete this (send error to webhook, log to cmd line, handle fatal error case)
@bot.tree.error
async def app_command_error(interaction: discord.Interaction, _: Union[Command, ContextMenu], error: AppCommandError):
    ctx = BlooContext(interaction)
    ctx.whisper = True
    if isinstance(error, CommandInvokeError):
        error = error.original

    if (isinstance(error, commands.MissingRequiredArgument)
            or isinstance(error, PermissionsFailure)
            or isinstance(error, commands.BadArgument)
            or isinstance(error, commands.BadUnionArgument)
            or isinstance(error, commands.MissingPermissions)
            or isinstance(error, commands.BotMissingPermissions)
            or isinstance(error, commands.MaxConcurrencyReached)
            or isinstance(error, commands.NoPrivateMessage)):
        await ctx.send_error(error)
    else:
        try:
            raise error
        except:
            tb = traceback.format_exc()
            logger.error(tb)
            if len(tb.split('\n')) > 8:
                tb = '\n'.join(tb.split('\n')[-8:])

            tb_formatted = tb
            if len(tb_formatted) > 1000:
                tb_formatted = "...\n" + tb_formatted[-1000:]

            await ctx.send_error(description=f"`{error}`\n```{tb_formatted}```")


@bot.event
async def on_ready():
    print("""
            88          88                          
            88          88                          
            88          88                          
            88,dPPYba,  88  ,adPPYba,   ,adPPYba,   
            88P'    "8a 88 a8"     "8a a8"     "8a  
            88       d8 88 8b       d8 8b       d8  
            88b,   ,a8" 88 "8a,   ,a8" "8a,   ,a8"  
            8Y"Ybbd8"'  88  `"YbbdP"'   `"YbbdP"'   \n""")
    logger.info(
        f'Logged in as: {bot.user.name} - {bot.user.id} ({discord.__version__})')
    logger.info(f'Successfully logged in and booted...!')

    await bot.issue_cache.fetch_issue_cache()
    await bot.rule_cache.fetch_rule_cache()
    await init_client_session()


async def main():
    async with bot:
        await bot.start(os.environ.get("BLOO_TOKEN"), reconnect=True)

asyncio.run(main())

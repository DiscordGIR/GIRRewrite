import asyncio
import os
import traceback
# Remove warning from songs cog
import warnings

import discord
from discord.app_commands import AppCommandError, CommandInvokeError, TransformerError
from discord.ext import commands

from core import Bot, MyTree
from utils import logger, GIRContext, scam_cache
from utils.framework import PermissionsFailure

warnings.simplefilter(action='ignore', category=FutureWarning)


intents = discord.Intents.all()
mentions = discord.AllowedMentions(everyone=False, users=True, roles=False)

bot = Bot(command_prefix='!', intents=intents, allowed_mentions=mentions, tree_cls=MyTree)

@bot.tree.error
async def app_command_error(interaction: discord.Interaction, error: AppCommandError):
    ctx = GIRContext(interaction)
    ctx.whisper = True
    if isinstance(error, CommandInvokeError):
        error = error.original

    if isinstance(error, discord.errors.NotFound):
        await ctx.channel.send(embed=discord.Embed(color=discord.Color.red(), title=":(\nYour command ran into a problem.", description=f"Sorry {interaction.user.mention}, it looks like I took too long to respond to you! If I didn't do what you wanted in time, please try again."), delete_after=7)
        return

    if (isinstance(error, commands.MissingRequiredArgument)
            or isinstance(error, PermissionsFailure)
            or isinstance(error, TransformerError)
            or isinstance(error, commands.BadArgument)
            or isinstance(error, commands.BadUnionArgument)
            or isinstance(error, commands.MissingPermissions)
            or isinstance(error, commands.BotMissingPermissions)
            or isinstance(error, commands.MaxConcurrencyReached)
            or isinstance(error, commands.NoPrivateMessage)):
        await ctx.send_error(error, followup=True, whisper=True, delete_after=5)
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

            await ctx.send_error(description=f"`{error}`\n```{tb_formatted}```", followup=True, whisper=True, delete_after=5)


@bot.event
async def on_ready():
    print("""
                      88             
                      ""             
                                     
           ,adPPYb,d8 88 8b,dPPYba,  
          a8"    `Y88 88 88P'   "Y8  
          8b       88 88 88          
          "8a,   ,d88 88 88          
           `"YbbdP"Y8 88 88          
           aa,    ,88                
            "Y8bbdP"              \n""")
    logger.info(
        f'Logged in as: {bot.user.name} - {bot.user.id} ({discord.__version__})')
    logger.info(f'Successfully logged in and booted...!')

    await bot.ban_cache.fetch_ban_cache()
    await bot.issue_cache.fetch_issue_cache()
    await bot.rule_cache.fetch_rule_cache()
    await scam_cache.fetch_scam_cache()


async def main():
    async with bot:
        await bot.start(os.environ.get("GIR_TOKEN"), reconnect=True)

asyncio.run(main())

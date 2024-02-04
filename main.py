import asyncio
import os
import traceback
import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import AppCommandError, Command, ContextMenu, CommandInvokeError, TransformerError
from extensions import initial_extensions
from utils import cfg, db, logger, GIRContext, BanCache, IssueCache, Tasks, RuleCache, init_client_session, scam_cache
from utils.framework import PermissionsFailure, gatekeeper, find_triggered_filters
from cogs.commands.context_commands import setup_context_commands

from typing import Union
from data.services.user_service import user_service

# Remove warning from songs cog
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)


intents = discord.Intents.all()
mentions = discord.AllowedMentions(everyone=False, users=True, roles=False)


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ban_cache = BanCache(self)
        self.issue_cache = IssueCache(self)
        self.rule_cache = RuleCache(self)

        # force the config object and database connection to be loaded
        if cfg and db and gatekeeper:
            logger.info("Presetup phase completed! Connecting to Discord...")

    async def setup_hook(self):
        bot.remove_command("help")
        for extension in initial_extensions:
            await self.load_extension(extension)

        setup_context_commands(self)

        self.tasks = Tasks(self)
        await init_client_session()


class MyTree(app_commands.CommandTree):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.bot:
            return False

        if gatekeeper.has(interaction.user.guild, interaction.user, 6):
            return True

        command = interaction.command

        if isinstance(interaction.command, discord.app_commands.ContextMenu):
            return True

        if command is None or interaction.type != discord.InteractionType.application_command:
            return True

        if command.parent is not None:
            command_name = f"{command.parent.name} {command.name}"
        else:
            command_name = command.name

        db_user = user_service.get_user(interaction.user.id)

        if db_user.command_bans.get(command_name):
            ctx = GIRContext(interaction)
            await ctx.send_error("You are not allowed to use that command!", whisper=True)
            return False

        options = interaction.data.get("options")
        if options is None or not options:
            return True

        message_content = ""
        for option in options:
            if option.get("type") == 1:
                for sub_option in option.get("options"):
                    message_content += str(sub_option.get("value")) + " "
            else:
                message_content += str(option.get("value")) + " "

        triggered_words = await find_triggered_filters(
            message_content, interaction.user)

        if triggered_words:
            ctx = GIRContext(interaction)
            await ctx.send_error("Your interaction contained a filtered word. Aborting!", whisper=True)
            return

        return True


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

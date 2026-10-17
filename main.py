import asyncio
from contextlib import suppress
import os
import traceback
from uuid import uuid4
import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import AppCommandError, Command, ContextMenu, CommandInvokeError, TransformerError
from extensions import initial_extensions
from utils import cfg, db, logger, GIRContext, BanCache, IssueCache, Tasks, RuleCache, init_client_session, scam_cache
from utils.framework import PermissionsFailure, gatekeeper, find_triggered_filters
from cogs.commands.context_commands import setup_context_commands

from typing import Union
from deploy.healthcheck import report_health
from data.services.user_service import user_service
from utils.fetchers import close_client_session
from utils.worker import BlockingIOPool
from data.database import configure_database_pool
from utils.health import monitor_runtime
from utils.logging import start_webhook_logging, stop_webhook_logging

# Remove warning from songs cog
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)


intents = discord.Intents.all()
mentions = discord.AllowedMentions(everyone=False, users=True, roles=False)


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deployment_ready = False
        self._deployment_initialized = False
        self._deployment_health_task = None
        self._startup_notified = False

        self.ban_cache = BanCache(self)
        self.issue_cache = IssueCache(self)
        self.rule_cache = RuleCache(self)

        # Validate the imported configuration and permission mapping.
        if cfg and db and gatekeeper:
            logger.info("Presetup phase completed! Connecting to Discord...")

    async def setup_hook(self):
        self.remove_command("help")
        await init_client_session()
        start_webhook_logging()
        self.database_io = BlockingIOPool(workers=4, name="gir-db")
        self.integration_io = BlockingIOPool(workers=2, name="gir-external")
        configure_database_pool(self.database_io)
        await self.database_io.run(db.connect)
        for extension in initial_extensions:
            await self.load_extension(extension)

        setup_context_commands(self)

        self.tasks = Tasks(self)
        self.health_task = asyncio.create_task(monitor_runtime(self, logger), name="runtime-health")
        if health_path := os.environ.get("GIR_HEALTH_FILE"):
            self._deployment_health_task = asyncio.create_task(report_health(self, health_path))

    async def notify_owner_of_startup(self):
        # on_ready can run again after a reconnect; notify only once per process.
        if self._startup_notified:
            return
        self._startup_notified = True
        revision = os.environ.get("GIR_REVISION", "")
        embed = discord.Embed(
            title="Bot started successfully",
            description=f"{self.user} is connected and startup caches have loaded.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow())
        if len(revision) == 40 and all(char in "0123456789abcdef" for char in revision):
            embed.add_field(
                name="Deployed commit",
                value=f"[{revision[:12]}](https://github.com/DiscordGIR/GIRRewrite/commit/{revision})",
                inline=False)
        else:
            embed.add_field(name="Deployed commit",
                            value="Unknown (not built by the deployment workflow).", inline=False)
        try:
            owner = await self.fetch_user(cfg.owner_id)
            await owner.send(embed=embed)
        except discord.HTTPException:
            logger.warning("Could not send the startup DM to the bot owner.", exc_info=True)

    async def close(self):
        if self._deployment_health_task is not None:
            self._deployment_health_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._deployment_health_task
        try:
            health_task = getattr(self, "health_task", None)
            if health_task is not None:
                health_task.cancel()
                await asyncio.gather(health_task, return_exceptions=True)
            if hasattr(self, "tasks"):
                self.tasks.close()
            await super().close()
        finally:
            await stop_webhook_logging()
            for name in ("database_io", "integration_io"):
                pool = getattr(self, name, None)
                if pool is not None:
                    await pool.close()
            await close_client_session()


class MyTree(app_commands.CommandTree):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.bot:
            return False
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
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

        db_user = await user_service.get_user(interaction.user.id)

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
            error_id = uuid4().hex[:12]
            logger.error("Command failed error_id=%s\n%s", error_id, traceback.format_exc())
            await ctx.send_error(description=f"Something went wrong. Please give a moderator this reference: `{error_id}`.", followup=True, whisper=True, delete_after=15)


@bot.event
async def on_ready():
    bot.deployment_ready = False
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

    bot.tasks.resume()
    for refresh in (bot.ban_cache.fetch_ban_cache, bot.issue_cache.fetch_issue_cache,
                    bot.rule_cache.fetch_rule_cache, scam_cache.fetch_scam_cache):
        try:
            await refresh()
        except Exception:
            logger.exception("Cache refresh failed: %s", refresh.__qualname__)
    bot._deployment_initialized = True
    bot.deployment_ready = True
    await bot.notify_owner_of_startup()


@bot.event
async def on_disconnect():
    bot.deployment_ready = False


@bot.event
async def on_resumed():
    bot.deployment_ready = bot._deployment_initialized



async def main():
    async with bot:
        await bot.start(os.environ.get("GIR_TOKEN"), reconnect=True)

if __name__ == "__main__":
    asyncio.run(main())

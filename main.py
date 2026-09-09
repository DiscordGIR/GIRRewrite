import asyncio
import os
import traceback
import json
import uuid
import tempfile
from pathlib import Path
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
from utils.runtime_paths import runtime_data_file

# Remove warning from songs cog
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)


# Keep the events GIR uses while avoiding presence and typing firehoses on very
# large servers. Member and message-content access are checked by the dashboard.
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = False
intents.typing = False
mentions = discord.AllowedMentions(everyone=False, users=True, roles=False)


def command_settings_path() -> Path:
    return Path(os.environ.get("GIR_COMMUNITY_FILE", runtime_data_file("community.json")))


def command_selection() -> set[str]:
    try:
        return set(json.loads(command_settings_path().read_text()).get("disabledCommands", []))
    except (OSError, ValueError, TypeError):
        return set()


def save_command_catalog(rows: list[dict]) -> None:
    path = command_settings_path().with_name("command-catalog.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="command-catalog.", dir=path.parent)
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump({"commands": rows}, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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

        guild = discord.Object(id=cfg.guild_id)
        available = self.tree.get_commands(guild=guild)
        command_type = lambda command: getattr(command, "type", discord.AppCommandType.chat_input)
        save_command_catalog([
            {
                "name": command.name,
                "description": getattr(command, "description", None) or "Right-click menu command",
                "type": int(command_type(command).value),
                "default_member_permissions": str(getattr(getattr(command, "default_permissions", None), "value", 0) or 0),
            }
            for command in available
        ])
        disabled = command_selection()
        for command in available:
            if command.name in disabled:
                self.tree.remove_command(command.name, guild=guild, type=command_type(command))

        # Keep slash commands current without requiring the owner to run !sync
        # after an update. GIR's commands are guild-scoped, so this takes effect
        # immediately in the configured server.
        if os.environ.get("GIR_SYNC_COMMANDS", "True") == "True":
            synced = await self.tree.sync(guild=guild)
            logger.info(f"Synced {len(synced)} application commands.")

        self.tasks = Tasks(self)
        await init_client_session()


class MyTree(app_commands.CommandTree):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.bot:
            return False

        command = interaction.command

        if command is not None:
            root_name = command.root_parent.name if command.root_parent else command.name
            disabled = command_selection()
            if root_name in disabled and interaction.user.id != cfg.owner_id:
                await interaction.response.send_message("That command is currently turned off for this server.", ephemeral=True)
                return False

        if gatekeeper.has(interaction.user.guild, interaction.user, 6):
            return True

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


bot = Bot(command_prefix='!', intents=intents, allowed_mentions=mentions, tree_cls=MyTree,
          chunk_guilds_at_startup=False, max_messages=5000)

@bot.tree.error
async def app_command_error(interaction: discord.Interaction, error: AppCommandError):
    ctx = GIRContext(interaction)
    ctx.whisper = True
    if isinstance(error, CommandInvokeError):
        error = error.original

    if isinstance(error, discord.errors.NotFound):
        try:
            await ctx.send_error("Discord says this command took too long. Please try it once more.", whisper=True)
        except discord.HTTPException:
            pass
        return

    if isinstance(error, discord.Forbidden):
        logger.error(f"Discord denied command {getattr(interaction.command, 'qualified_name', 'unknown')}: {error}")
        await ctx.send_error(
            "Discord blocked that action. GIR has its moderation permission, but its role may be below the selected member's role. Ask the server owner to move GIR higher in Server Settings → Roles.",
            followup=True, whisper=True)
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
        reference = uuid.uuid4().hex[:8]
        logger.error(f"Command error reference {reference}\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}")
        try:
            await ctx.send_error(
                description=f"Something unexpected happened. The private server log has reference `{reference}`.",
                followup=True, whisper=True)
        except discord.HTTPException:
            logger.error(f"Could not deliver command error reference {reference} to Discord")


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

if __name__ == "__main__":
    asyncio.run(main())

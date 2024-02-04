import functools

import discord
from discord import app_commands, Interaction
from discord.ext.commands.errors import BadArgument
from utils import GIRContext
from .permissions import gatekeeper
from utils.config import cfg


class PermissionsFailure(discord.app_commands.AppCommandError):
    def __init__(self, message):
        super().__init__(message)


def whisper(func: discord.app_commands.Command):
    """If the user is not a moderator and the invoked channel is not #bot-commands, send the response to the command ephemerally"""

    @functools.wraps(func)
    async def decorator(self, ctx: GIRContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and ctx.channel.id != cfg.channels.bot_commands:
            ctx.whisper = True
        else:
            ctx.whisper = False
        await func(self, ctx, *args, **kwargs)

    return decorator


def whisper_in_general(func: discord.app_commands.Command):
    """If the user is not a moderator and the invoked channel is #general, send the response to the command ephemerally"""
    @functools.wraps(func)
    async def decorator(self, ctx: GIRContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and ctx.channel.id == cfg.channels.general:
            ctx.whisper = True
        else:
            ctx.whisper = False
        await func(self, ctx, *args, **kwargs)

    return decorator


def whisper_outside_jb_and_geniusbar_unless_genius(func: discord.app_commands.Command):
    """If the user is not a Genius and the invoked channel is not #jailbreak, #genius-bar, #bot-commands, send the response to the command ephemerally"""
    @functools.wraps(func)
    async def decorator(self, ctx: GIRContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 4) and ctx.channel.id not in [cfg.channels.jailbreak, cfg.channels.genius_bar, cfg.channels.bot_commands]:
            ctx.whisper = True
        else:
            ctx.whisper = False
        await func(self, ctx, *args, **kwargs)

    return decorator

def always_whisper(func: discord.app_commands.Command):
    """Always respond ephemerally"""
    @functools.wraps(func)
    async def decorator(self, ctx: GIRContext, *args, **kwargs):
        ctx.whisper = True
        await func(self, ctx, *args, **kwargs)

    return decorator


def memplus_and_up():
    """If the user is not at least a Member Plus, deny command access"""
    async def predicate(interaction: Interaction):
        if not gatekeeper.has(interaction.guild, interaction.user, 1):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)


def mempro_and_up():
    """If the user is not at least a Member Pro, deny command access"""
    async def predicate(interaction: Interaction):
        if not gatekeeper.has(interaction.guild, interaction.user, 2):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)


def memed_and_up():
    """If the user is not at least a Member Edition, deny command access"""
    async def predicate(interaction: Interaction):
        if not gatekeeper.has(interaction.guild, interaction.user, 3):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)


def genius_and_up():
    """If the member is not at least a Genius™️, deny command access"""
    async def predicate(interaction: Interaction):
        if not gatekeeper.has(interaction.guild, interaction.user, 4):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)

####################
# Staff Roles
####################


def submod_or_admin_and_up():
    """If the user is not a submod OR is not at least an Administrator, deny command access"""
    async def predicate(interaction: Interaction):
        submod = interaction.guild.get_role(cfg.roles.sub_mod)
        if not submod:
            return

        if not (gatekeeper.has(interaction.guild, interaction.user, 6) or submod in interaction.user.roles):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)


def genius_or_submod_and_up():
    """If the user is not at least a Genius™️ or a submod, deny command access"""
    async def predicate(interaction: Interaction):
        submod = interaction.guild.get_role(cfg.roles.sub_mod)
        if not submod:
            return

        if not (gatekeeper.has(interaction.guild, interaction.user, 4) or submod in interaction.user.roles):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)


def mod_and_up():
    """If the user is not at least a Moderator, deny command access"""
    async def predicate(interaction: Interaction):
        if not gatekeeper.has(interaction.guild, interaction.user, 5):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)


def admin_and_up():
    """If the user is not at least an Administrator, deny command access"""
    async def predicate(interaction: Interaction):
        if not gatekeeper.has(interaction.guild, interaction.user, 6):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)

####################
# Other
####################


def guild_owner_and_up():
    """If the user is not the guild owner, deny command access"""
    async def predicate(interaction: Interaction):
        if not gatekeeper.has(interaction.guild, interaction.user, 7):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)


def bot_owner_and_up():
    """If the user is not the bot owner, deny command access"""
    async def predicate(interaction: Interaction):
        if not gatekeeper.has(interaction.guild, interaction.user, 9):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        return True
    return app_commands.check(predicate)


def ensure_invokee_role_lower_than_bot():
    """If the invokee's role is higher than the bot's, deny command access"""
    async def predicate(interaction: Interaction):
        if interaction.guild.me.top_role < interaction.user.top_role:
            raise PermissionsFailure(
                f"Your top role is higher than mine. I can't change your nickname :(")

        return True
    return app_commands.check(predicate)

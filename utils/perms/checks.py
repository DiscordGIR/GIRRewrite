import functools

import discord
from data.services import guild_service
from discord.ext.commands.errors import BadArgument
from .permissions import gatekeeper
from utils.context import BlooContext


class PermissionsFailure(BadArgument):
    def __init__(self, message):
        super().__init__(message)


def whisper(func: discord.app_commands.Command):
    """If the user is not a moderator and the invoked channel is not #bot-commands, send the response to the command ephemerally"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and ctx.channel.id != guild_service.get_guild().channel_botspam:
            ctx.whisper = True
        else:
            ctx.whisper = False
        await func(self, ctx, *args, **kwargs)

    return decorator


def whisper_in_general(func: discord.app_commands.Command):
    """If the user is not a moderator and the invoked channel is #general, send the response to the command ephemerally"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and ctx.channel.id == guild_service.get_guild().channel_general:
            ctx.whisper = True
        else:
            ctx.whisper = False
        await func(self, ctx, *args, **kwargs)
    return decorator


def memplus_and_up(func: discord.app_commands.Command):
    """If the user is not at least a Member Plus, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 1):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator


def mempro_and_up(func: discord.app_commands.Command):
    """If the user is not at least a Member Pro, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 2):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator


def memed_and_up(func: discord.app_commands.Command):
    """If the user is not at least a Member Edition, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 3):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator


def genius_and_up(func: discord.app_commands.Command):
    """If the member is not at least a Genius™️, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 4):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator

####################
# Staff Roles
####################


def submod_or_admin_and_up(func: discord.app_commands.Command):
    """If the user is not a submod OR is not at least an Administrator, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        db = guild_service.get_guild()
        submod = ctx.guild.get_role(db.role_sub_mod)
        if not submod:
            return

        if not (gatekeeper.has(ctx.guild, ctx.author, 6) or submod in ctx.author.roles):
            raise BadArgument(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator


def genius_or_submod_and_up(func: discord.app_commands.Command):
    """If the user is not at least a Genius™️ or a submod, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        db = guild_service.get_guild()
        submod = ctx.guild.get_role(db.role_sub_mod)
        if not submod:
            return

        if not (gatekeeper.has(ctx.guild, ctx.author, 4) or submod in ctx.author.roles):
            raise BadArgument(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator


def mod_and_up(func: discord.app_commands.Command):
    """If the user is not at least a Moderator, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 5):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator


def admin_and_up(func: discord.app_commands.Command):
    """If the user is not at least an Administrator, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 6):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator

####################
# Other
####################


def guild_owner_and_up(func: discord.app_commands.Command):
    """If the user is not the guild owner, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 7):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator


def bot_owner_and_up(func: discord.app_commands.Command):
    """If the user is not the bot owner, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if not gatekeeper.has(ctx.guild, ctx.author, 9):
            raise PermissionsFailure(
                "You do not have permission to use this command.")

        await func(self, ctx, *args, **kwargs)
    return decorator


def ensure_invokee_role_lower_than_bot(func: discord.app_commands.Command):
    """If the invokee's role is higher than the bot's, deny command access"""
    @functools.wraps(func)
    async def decorator(self, ctx: BlooContext, *args, **kwargs):
        if ctx.me.top_role < ctx.author.top_role:
            raise PermissionsFailure(
                f"Your top role is higher than mine. I can't change your nickname :(")

        await func(self, ctx, *args, **kwargs)
    return decorator

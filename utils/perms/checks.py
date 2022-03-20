import functools
import discord
from data.services import guild_service

from utils.context import BlooContext
from utils import gatekeeper

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
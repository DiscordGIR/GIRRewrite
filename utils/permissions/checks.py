import functools
import discord

from utils.context import BlooContext

def whisper(func: discord.app_commands.Command):
    """If the user is not a moderator and the invoked channel is not #bot-commands, send the response to the command ephemerally"""
    async def decorator(*args, **kwargs):
        # ctx.whisper = True
        print(args)
        print(kwargs)
        await func(*args, **kwargs)
        # if not permissions.has(ctx.guild, ctx.author, 5) and ctx.channel.id != guild_service.get_guild().channel_botspam:
        #     ctx.whisper = True
        # else:
        #     ctx.whisper = False
        # return True
    # return commands.check(predicate)
    return decorator
from typing import Union

import discord
from discord.ext import commands

from core import get_session
from core.service import UserXpService, UserService
from utils import GIRContext
from utils.framework import gatekeeper


async def handle_userinfo(ctx: GIRContext, user: Union[discord.Member, discord.User]):
    is_mod = gatekeeper.has(ctx.guild, ctx.author, 5)
    if user is None:
        user = ctx.author

    # is the invokee in the guild?
    if isinstance(user, discord.User) and not is_mod:
        raise commands.BadArgument(
            "You do not have permission to use this command.")

    # non-mods are only allowed to request their own userinfo
    if not is_mod and user.id != ctx.author.id:
        raise commands.BadArgument(
            "You do not have permission to use this command.")

    async with get_session(ctx.bot.engine) as session:
        user_xp_service = UserXpService(session)
        user_service = UserService(session)
        xp = await user_xp_service.get_xp(user.id)

    embed = await user_service.get_userinfo_embed(ctx, user, xp)

    return embed
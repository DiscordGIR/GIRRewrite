from datetime import datetime
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

from cogs.shared import handle_userinfo
from core import get_session
from core.bot import Bot
from core.service import UserService, UserXpService, CaseService
from utils import GIRContext, cfg, transform_context
from utils.framework import PermissionsFailure, gatekeeper, whisper


class UserInfo(commands.Cog):
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot
        self.start_time = datetime.now()

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get info of another user or yourself.")
    @app_commands.describe(user="User to get info of")
    @transform_context
    @whisper
    async def userinfo(self, ctx: GIRContext, user: Union[discord.Member, discord.User] = None) -> None:
        embed = await handle_userinfo(ctx, user)
        await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Show your or another user's XP")
    @app_commands.describe(member="Member to get XP of")
    @transform_context
    @whisper
    async def xp(self, ctx: GIRContext, member: discord.Member = None) -> None:
        if member is None:
            member = ctx.author

        async with get_session(self.bot.engine) as session:
            user_xp_service = UserXpService(session)
            user_xp = await user_xp_service.get_xp(member.id)

        embed = user_xp_service.get_xp_embed(member, user_xp)

        await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Show your or another member's warnpoints")
    @app_commands.describe(member="Member to get warnpoints of")
    @transform_context
    @whisper
    async def warnpoints(self, ctx: GIRContext, member: discord.Member = None):
        # if member is not provided, default to the invoker
        member = member or ctx.author

        # users can only invoke on themselves if they aren't mods
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and member.id != ctx.author.id:
            raise PermissionsFailure(
                f"You don't have permissions to check others' warnpoints.")

        # fetch user profile from database
        async with get_session(self.bot.engine) as session:
            user_service = UserService(session)
            warn_points = await user_service.get_user_warn_points(member.id)

        embed = user_service.get_warn_points_embed(member, warn_points)

        await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Show the XP leaderboard.")
    @transform_context
    @whisper
    async def xptop(self, ctx: GIRContext):
        async with get_session(self.bot.engine) as session:
            user_xp_service = UserXpService(session)
            leaderboard = await user_xp_service.get_leaderboard()

        if not leaderboard:
            return await ctx.send_warning("No users found in the leaderboard.", delete_after=5)

        menu = user_xp_service.create_xptop_menu(ctx, leaderboard)
        await menu.start()

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Show your or another user's cases")
    @app_commands.describe(user="User to get cases of")
    @transform_context
    @whisper
    async def cases(self, ctx: GIRContext, user: Union[discord.Member, discord.User] = None):
        """Show list of cases of a user (mod only)

        Example usage
        --------------
        /cases user:<@user/ID>

        Parameters
        ----------
        ctx : GIRContext
            "The context of the command"
        user : discord.Member, optional
            "User we want to get cases of, doesn't have to be in guild"

        """

        # if an invokee is not provided in command, call command on the invoker
        # (get invoker's cases)
        if user is None:
            user = ctx.author

        # users can only invoke on themselves if they aren't mods
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and user.id != ctx.author.id:
            raise PermissionsFailure(
                f"You don't have permissions to check others' cases.")

        # fetch user's cases from our database
        async with get_session(self.bot.engine) as session:
            case_service = CaseService(session)
            cases = await case_service.get_user_cases(user.id)

        if not cases:
            return await ctx.send_warning(f'{user.mention} has no cases.', delete_after=5)

        menu = case_service.create_cases_menu(ctx, user, cases)
        await menu.start()


async def setup(bot):
    await bot.add_cog(UserInfo(bot))


from datetime import datetime
from math import floor
from typing import Union

import discord

from core import Bot, get_session
# from data_mongo.services import user_service
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt

from core.service import UserService
from utils import GIRContext, cfg, transform_context
from utils.framework import PermissionsFailure, gatekeeper, whisper
from utils.views import Menu


def format_xptop_page(ctx, entries, current_page, all_pages):
    """Formats the page for the xptop embed.

    Parameters
    ----------
    entry : dict
        "The dictionary for the entry"
    all_pages : list
        "All entries that we will eventually iterate through"
    current_page : number
        "The number of the page that we are currently on"

    Returns
    -------
    discord.Embed
        "The embed that we will send"

    """
    embed = discord.Embed(title=f'Leaderboard', color=discord.Color.blurple())
    for i, user in entries:
        member = ctx.guild.get_member(user._id)
        trophy = ''
        if current_page == 1:
            if i == entries[0][0]:
                trophy = ':first_place:'
                embed.set_thumbnail(url=member.avatar)
            if i == entries[1][0]:
                trophy = ':second_place:'
            if i == entries[2][0]:
                trophy = ':third_place:'

        embed.add_field(name=f"#{i+1} - Level {user.level}",
                        value=f"{trophy} {member.mention}", inline=False)

    embed.set_footer(text=f"Page {current_page} of {len(all_pages)}")
    return embed


def format_cases_page(ctx, entries, current_page, all_pages):
    """Formats the page for the cases embed.

    Parameters
    ----------
    entry : dict
        "The dictionary for the entry"
    all_pages : list
        "All entries that we will eventually iterate through"
    current_page : number
        "The number of the page that we are currently on"

    Returns
    -------
    discord.Embed
        "The embed that we will send"

    """
    page_count = 0

    user = ctx.case_user
    u = user_service.get_user(user.id)

    for page in all_pages:
        for case in page:
            page_count = page_count + 1
    embed = discord.Embed(
        title=f'Cases - {u.warn_points} warn points', color=discord.Color.blurple())
    embed.set_author(name=user, icon_url=user.display_avatar)
    for case in entries:
        timestamp = case.date
        formatted = f"{format_dt(timestamp, style='F')} ({format_dt(timestamp, style='R')})"
        if case._type == "WARN" or case._type == "LIFTWARN":
            if case.lifted:
                embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id} [LIFTED]',
                                value=f'**Points**: {case.punishment}\n**Reason**: {case.reason}\n**Lifted by**: {case.lifted_by_tag}\n**Lift reason**: {case.lifted_reason}\n**Warned on**: {formatted}', inline=True)
            elif case._type == "LIFTWARN":
                embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id} [LIFTED (legacy)]',
                                value=f'**Points**: {case.punishment}\n**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Warned on**: {formatted}', inline=True)
            else:
                embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id}',
                                value=f'**Points**: {case.punishment}\n**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Warned on**: {formatted}', inline=True)
        elif case._type == "MUTE" or case._type == "REMOVEPOINTS":
            embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id}',
                            value=f'**{pun_map[case._type]}**: {case.punishment}\n**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Time**: {formatted}', inline=True)
        elif case._type in pun_map:
            embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id}',
                            value=f'**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**{pun_map[case._type]} on**: {formatted}', inline=True)
        else:
            embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id}',
                            value=f'**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Time**: {formatted}', inline=True)
    embed.set_footer(
        text=f"Page {current_page} of {len(all_pages)} - newest cases first ({page_count} total cases)")
    return embed


pun_map = {
    "KICK": "Kicked",
    "BAN": "Banned",
    "CLEM": "Clemmed",
    "UNBAN": "Unbanned",
    "MUTE": "Duration",
    "REMOVEPOINTS": "Points removed"
}


def determine_emoji(type):
    emoji_dict = {
        "KICK": "👢",
        "BAN": "❌",
        "UNBAN": "✅",
        "MUTE": "🔇",
        "WARN": "⚠️",
        "UNMUTE": "🔈",
        "LIFTWARN": "⚠️",
        "REMOVEPOINTS": "⬇️",
        "CLEM": "👎"
    }
    return emoji_dict[type]


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
        await handle_userinfo(ctx, user)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Show your or another user's XP")
    @app_commands.describe(member="Member to get XP of")
    @transform_context
    @whisper
    async def xp(self, ctx: GIRContext, member: discord.Member = None) -> None:
        if member is None:
            member = ctx.author

        async with get_session(self.bot.engine) as session:
            user_service = UserService(session)
            user_xp = await user_service.get_leaderboard_rank(member.id)

        embed = discord.Embed(title="Level Statistics")
        embed.color = member.top_role.color
        embed.set_author(name=member, icon_url=member.display_avatar)
        embed.add_field(
            name="Level", value=user_xp.level if not user_xp.is_clem else "0", inline=True)
        embed.add_field(
            name="XP", value=f'{user_xp.xp}/{xp_for_next_level(user_xp.level)}' if not user_xp.is_clem else "0/0", inline=True)

        embed.add_field(
            name="Rank", value=f"{user_xp.rank}/{user_xp.total_count}" if not user_xp.is_clem else f"{user_xp.total_count}/{user_xp.total_count}", inline=True)

        await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Show your or another member's warnpoints")
    @app_commands.describe(member="Member to get warnpoints of")
    @transform_context
    @whisper
    async def warnpoints(self, ctx: GIRContext, member: discord.Member = None):
        # if an invokee is not provided in command, call command on the invoker
        # (get invoker's warnpoints)
        member = member or ctx.author

        # users can only invoke on themselves if they aren't mods
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and member.id != ctx.author.id:
            raise PermissionsFailure(
                f"You don't have permissions to check others' warnpoints.")

        # fetch user profile from database
        results = user_service.get_user(member.id)

        embed = discord.Embed(title="Warn Points",
                              color=discord.Color.orange())
        embed.set_thumbnail(url=member.display_avatar)
        embed.add_field(
            name="Member", value=f'{member.mention}\n{member}\n({member.id})', inline=True)
        embed.add_field(name="Warn Points",
                        value=results.warn_points, inline=True)

        await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Show the XP leaderboard.")
    @transform_context
    @whisper
    async def xptop(self, ctx: GIRContext):
        results = enumerate(user_service.leaderboard())
        results = [(i, m) for (i, m) in results if ctx.guild.get_member(
            m._id) is not None][0:100]

        menu = Menu(ctx, results, per_page=10,
                    page_formatter=format_xptop_page, whisper=ctx.whisper)
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
        results = user_service.get_cases(user.id)
        if len(results.cases) == 0:
            return await ctx.send_warning(f'{user.mention} has no cases.', delete_after=5)

        # filter out unmute cases because they are irrelevant
        cases = [case for case in results.cases if case._type != "UNMUTE"]
        # reverse so newest cases are first
        cases.reverse()

        ctx.case_user = user

        menu = Menu(ctx, cases, per_page=10,
                    page_formatter=format_cases_page, whisper=ctx.whisper)
        await menu.start()


def xp_for_next_level(_next):
    """Magic formula to determine XP thresholds for levels
    """

    level = 0
    xp = 0

    for _ in range(0, _next):
        xp = xp + 45 * level * (floor(level / 10) + 1)
        level += 1

    return xp


async def setup(bot):
    await bot.add_cog(UserInfo(bot))


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

    # prepare list of roles and join date
    roles = ""
    if isinstance(user, discord.Member) and user.joined_at is not None:
        reversed_roles = user.roles
        reversed_roles.reverse()

        for role in reversed_roles[:-1]:
            roles += role.mention + " "
        joined = f"{format_dt(user.joined_at, style='F')} ({format_dt(user.joined_at, style='R')})"
    else:
        roles = "No roles."
        joined = f"User not in {ctx.guild}"

    results = user_service.get_user(user.id)

    embed = discord.Embed(title=f"User Information", color=user.color)
    embed.set_author(name=user)
    embed.set_thumbnail(url=user.display_avatar)
    embed.add_field(name="Username",
                    value=f'{user} ({user.mention})', inline=True)
    embed.add_field(
        name="Level", value=results.level if not results.is_clem else "0", inline=True)
    embed.add_field(
        name="XP", value=results.xp if not results.is_clem else "0/0", inline=True)
    embed.add_field(
        name="Roles", value=roles[:1024] if roles else "None", inline=False)
    embed.add_field(
        name="Join date", value=joined, inline=True)
    embed.add_field(name="Account creation date",
                    value=f"{format_dt(user.created_at, style='F')} ({format_dt(user.created_at, style='R')})", inline=True)

    if user.banner is None and isinstance(user, discord.Member):
        user = await ctx.bot.fetch_user(user.id)

    if user.banner is not None:
        embed.set_image(url=user.banner.url)

    await ctx.respond(embed=embed, ephemeral=ctx.whisper)

from typing import Union

import discord
from discord.utils import format_dt
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.user.warn_points_result import WarnPointsResult
from core.repository import UserRepository
from utils import GIRContext


class UserService:
    def __init__(self, session: AsyncSession):
        self._user_repository = UserRepository(session)

    async def get_user_warn_points(self, user_id: int) -> WarnPointsResult:
        warn_points = await self._user_repository.get_user_warn_points(user_id)
        return warn_points

    def get_warn_points_embed(self, member: discord.Member, warn_points_result: WarnPointsResult) -> discord.Embed:
        embed = discord.Embed(title="Warn Points",
                              color=discord.Color.orange())
        embed.set_thumbnail(url=member.display_avatar)
        embed.add_field(
            name="Member", value=f'{member.mention}\n{member}\n({member.id})', inline=True)
        embed.add_field(name="Warn Points",
                        value=warn_points_result.points, inline=True)

        return embed

    async def get_userinfo_embed(self, ctx: GIRContext, user: Union[discord.Member, discord.User], xp) -> discord.Embed:
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

        embed = discord.Embed(title=f"User Information", color=user.color)
        embed.set_author(name=user)
        embed.set_thumbnail(url=user.display_avatar)
        embed.add_field(name="Username",
                        value=f'{user} ({user.mention})', inline=True)

        embed.add_field(
            name="Level", value=xp.level if not xp.is_clem else "0", inline=True)
        embed.add_field(
            name="XP", value=xp.xp if not xp.is_clem else "0/0", inline=True)
        embed.add_field(
            name="Roles", value=roles[:1024] if roles else "None", inline=False)
        embed.add_field(
            name="Join date", value=joined, inline=True)
        embed.add_field(name="Account creation date",
                        value=f"{format_dt(user.created_at, style='F')} ({format_dt(user.created_at, style='R')})",
                        inline=True)

        if user.banner is None and isinstance(user, discord.Member):
            user = await ctx.bot.fetch_user(user.id)

        if user.banner is not None:
            embed.set_image(url=user.banner.url)

        return embed
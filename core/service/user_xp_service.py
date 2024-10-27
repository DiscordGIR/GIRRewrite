from typing import List

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from core.ui import format_xptop_page
from core.util import xp_for_next_level
from core.domain import UserXpAndLeaderboardRank, LeaderboardEntry
from core.repository import UserRepository
from utils.views.menus.menu import Menu


class UserXpService:
    def __init__(self, session: AsyncSession):
        self._user_repository = UserRepository(session)

    async def get_xp(self, user_id: int) -> UserXpAndLeaderboardRank:
        xp_info = await self._user_repository.get_user_xp_and_rank(user_id)
        return xp_info

    async def get_leaderboard(self) -> List[LeaderboardEntry]:
        leaderboard_results = await self._user_repository.get_leaderboard(top_user_count=130)
        return leaderboard_results

    def get_xp_embed(self, member: discord.Member, user_xp: UserXpAndLeaderboardRank) -> discord.Embed:
        embed = discord.Embed(title="Level Statistics")
        embed.color = member.top_role.color
        embed.set_author(name=member, icon_url=member.display_avatar)
        embed.add_field(
            name="Level", value=user_xp.level if not user_xp.is_clem else "0", inline=True)
        embed.add_field(
            name="XP", value=f'{user_xp.xp}/{xp_for_next_level(user_xp.level)}' if not user_xp.is_clem else "0/0",
            inline=True)

        embed.add_field(
            name="Rank",
            value=f"{user_xp.rank}/{user_xp.total_user_count}" if not user_xp.is_clem else f"{user_xp.total_user_count}/{user_xp.total_user_count}",
            inline=True
        )

        return embed

    def create_xptop_menu(self, ctx, leaderboard) -> Menu:
        leaderboard = [entry for entry in leaderboard if ctx.guild.get_member(
            entry.user_id) is not None][0:100]

        menu = Menu(ctx, leaderboard, per_page=10,
                    page_formatter=format_xptop_page, whisper=ctx.whisper)

        return menu
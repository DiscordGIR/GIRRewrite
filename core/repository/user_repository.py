from typing import List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain import UserXpAndLeaderboardRank, LeaderboardEntry
from core.domain.user.warn_points_result import WarnPoints
from core.model import User


class UserRepository:
    session: AsyncSession

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_xp_and_rank(self, user_id) -> UserXpAndLeaderboardRank:
        # Subquery to get the user's XP for comparison
        user_xp_subquery = select(User.xp).where(User.user_id == user_id).scalar_subquery()

        # Subquery to count users with XP greater than or equal to the target user's XP
        subquery_rank = (
            select(func.count(User.user_id))
            .where(User.xp >= user_xp_subquery)
            .scalar_subquery()
        )

        # Subquery for total user count
        subquery_total_users = select(func.count()).select_from(User).scalar_subquery()

        # Main query to get the user's XP, level, rank, and total count
        stmt = (
            select(
                User.xp,
                User.level,
                User.is_clem,
                subquery_rank.label("rank"),
                subquery_total_users.label("total_user_count")
            )
            .where(User.user_id == user_id)
        )

        result = await self.session.execute(stmt)
        xp, level, is_clem, rank, total_user_count = result.one_or_none()

        return UserXpAndLeaderboardRank(
            user_id=user_id,
            xp=xp,
            level=level,
            is_clem=is_clem,
            rank=rank,
            total_user_count=total_user_count
        )

    async def get_user_warn_points(self, user_id) -> WarnPoints:
        stmt = select(User.warn_points).where(User.user_id == user_id)
        result = await self.session.execute(stmt)
        warn_points = result.scalar()

        return WarnPoints(user_id=user_id, warn_points=warn_points)

    async def get_leaderboard(self, top_user_count) -> List[LeaderboardEntry]:
        stmt = (
            select(
                User.user_id,
                User.xp,
                User.level,
                func.row_number().over(order_by=User.xp.desc()).label("rank")
            )
            .order_by(User.xp.desc())
            .limit(top_user_count)
        )

        result = await self.session.execute(stmt)
        leaderboard_entries = result.all()

        return [LeaderboardEntry(user_id=user_id, xp=xp, level=level, rank=rank) for user_id, xp, level, rank in leaderboard_entries]



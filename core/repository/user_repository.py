from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain import UserXpAndLeaderboardRank
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
            xp=xp,
            level=level,
            is_clem=is_clem,
            rank=rank,
            total_user_count=total_user_count
        )


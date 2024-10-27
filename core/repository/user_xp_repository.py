from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain import UserXpAndLeaderboardRank
from core.model import UserXp


class UserXpRepository:
    session: AsyncSession

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_xp_and_rank(self, user_id) -> UserXpAndLeaderboardRank:
        # Subquery to get the user's XP for comparison
        user_xp_subquery = select(UserXp.xp).where(UserXp.user_id == user_id).scalar_subquery()

        # Subquery to count users with XP greater than or equal to the target user's XP
        subquery_rank = (
            select(func.count(UserXp.user_id))
            .where(UserXp.xp >= user_xp_subquery)
            .scalar_subquery()
        )

        # Subquery for total user count
        subquery_total_users = select(func.count()).select_from(UserXp).scalar_subquery()

        # Main query to get the user's XP, level, rank, and total count
        stmt = (
            select(
                UserXp.xp,
                UserXp.level,
                subquery_rank.label("rank"),
                subquery_total_users.label("total_user_count")
            )
            .where(UserXp.user_id == user_id)
        )

        result = await self.session.execute(stmt)
        xp, level, rank, total_user_count = result.one_or_none()

        return UserXpAndLeaderboardRank(xp, level, rank, total_user_count, False)


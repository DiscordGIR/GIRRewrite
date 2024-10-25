from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain import UserXpResult
from core.model import UserXp


class UserXpRepository:
    session: AsyncSession

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_xp_stats(self, user_id: int) -> UserXpResult:
        # Query to get the user xp
        user_xp_stmt = (
            select(UserXp.xp, UserXp.level)
            .where(UserXp.user_id == user_id)
        )

        user_xp_result = await self.session.execute(user_xp_stmt)
        xp, level = user_xp_result.one_or_none()

        # Query to calculate Rank and TotalCount
        rank_stmt = (
            select(
                func.count().filter(UserXp.xp >= xp).label('Rank'),
                func.count().label('TotalCount')
            )
            .select_from(UserXp)
        )

        rank_result = await self.session.execute(rank_stmt)
        rank, total_count = rank_result.one_or_none()

        return UserXpResult(xp, level, rank, total_count)

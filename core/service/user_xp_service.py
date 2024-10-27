from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain import UserXpAndLeaderboardRank, LeaderboardEntry
from core.repository import UserRepository


class UserXpService:
    def __init__(self, session: AsyncSession):
        self._user_repository = UserRepository(session)

    async def get_xp(self, user_id: int) -> UserXpAndLeaderboardRank:
        xp_info = await self._user_repository.get_user_xp_and_rank(user_id)
        return xp_info

    async def get_leaderboard(self) -> List[LeaderboardEntry]:
        leaderboard_results = await self._user_repository.get_leaderboard(top_user_count=130)
        return leaderboard_results
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain import UserXpAndLeaderboardRank
from core.repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession):
        self.user_repository = UserRepository(session)

    async def get_xp(self, user_id: int) -> UserXpAndLeaderboardRank:
        xp_info = await self.user_repository.get_user_xp_and_rank(user_id)
        return xp_info

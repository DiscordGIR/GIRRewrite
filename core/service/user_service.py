from sqlalchemy.ext.asyncio import AsyncSession

from core.domain import UserXpResult
from core.repository.user_xp_repository import UserXpRepository


class UserService:
    def __init__(self, session: AsyncSession):
        self.user_xp_repository = UserXpRepository(session)

    # def get_user(self, user_id: int):
    #     return self.user_repo.get_user(user_id)

    async def get_leaderboard_rank(self, xp: int) -> UserXpResult:
        return await self.user_xp_repository.get_user_xp_stats(xp)

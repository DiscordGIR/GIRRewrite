from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.user.warn_points_result import WarnPoints
from core.repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession):
        self._user_repository = UserRepository(session)

    async def get_user_warn_points(self, user_id: int) -> WarnPoints:
        warn_points = await self._user_repository.get_user_warn_points(user_id)
        return warn_points

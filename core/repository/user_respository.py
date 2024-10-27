from sqlalchemy.ext.asyncio import AsyncSession

from core.model import User


class UserRepository:
    session: AsyncSession

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int):
        return await self.session.get(User, user_id)

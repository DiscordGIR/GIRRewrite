from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.case import CaseResult
from core.repository import CaseRepository, UserRepository


class CaseService:
    def __init__(self, session: AsyncSession):
        self._case_repository = CaseRepository(session)
        self._user_repository = UserRepository(session)

    async def get_user_cases(self, user_id: int) -> List[CaseResult]:
        case_result = await self._case_repository.get_user_cases(user_id)

        return case_result
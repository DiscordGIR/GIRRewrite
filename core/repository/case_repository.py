from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.case import CaseResult
from core.model import Case, User


class CaseRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_user_cases(self, user_id: int) -> List[CaseResult]:
        stmt = (
            select(Case, User.warn_points)
            .join(User, Case.user_id == User.user_id)
            .filter(Case.user_id == user_id)
            .order_by(Case.date.desc())
        )
        result = await self._session.execute(stmt)
        cases = result.all()

        return [CaseResult.from_orm(case, warn_points) for case, warn_points in cases]

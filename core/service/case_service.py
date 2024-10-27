from typing import List, Union

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.case import CaseResult
from core.repository import CaseRepository, UserRepository
from core.ui import format_cases_page
from utils import GIRContext
from utils.views.menus.menu import Menu


class CaseService:
    def __init__(self, session: AsyncSession):
        self._case_repository = CaseRepository(session)
        self._user_repository = UserRepository(session)

    async def get_user_cases(self, user_id: int) -> List[CaseResult]:
        case_result = await self._case_repository.get_user_cases(user_id)

        return case_result

    def create_cases_menu(self, ctx: GIRContext, user: Union[discord.Member, discord.User], cases: List[CaseResult]) -> Menu:
        # filter out unmute cases because they are irrelevant
        cases = [case for case in cases if case.punishment != "UNMUTE"]

        ctx.target = user

        menu = Menu(ctx, cases, per_page=10,
                    page_formatter=format_cases_page, whisper=ctx.whisper)

        return menu

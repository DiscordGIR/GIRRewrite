from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain import TagResult
from core.model import Tag, TagButton


class TagRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_tag(self, name: str) -> Optional[TagResult]:
        stmt = (
            # select Tag and all tag buttons where the name matches
            select(Tag, TagButton)
            .join(TagButton)
            .where(Tag.name == name)
        )
        result = await self.session.execute(stmt)

        tag_and_buttons = result.one_or_none()
        if tag_and_buttons is None:
            return None

        tag, button = tag_and_buttons
        return TagResult(tag, button)

    async def get_all_tags(self) -> List[Tag]:
        stmt = select(Tag).order_by(Tag.phrase)
        result = await self.session.execute(stmt)
        tags = list(result.scalars().all())

        return tags
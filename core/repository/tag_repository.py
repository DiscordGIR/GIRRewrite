from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain import TagResult, TagToCreate
from core.model import Tag, TagButton


class TagRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_tag(self, name: str) -> Optional[TagResult]:
        stmt = (
            select(Tag, TagButton)
            .join(TagButton, isouter=True)
            .where(Tag.phrase == name)
        )

        result = await self.session.execute(stmt)

        tag_and_buttons = result.all()
        if not tag_and_buttons:
            return None

        tag = None
        buttons = []
        for row in tag_and_buttons:
            tag, button = row
            if button:
                buttons.append(button)

        return TagResult(tag, buttons)

    async def get_all_tags(self) -> List[Tag]:
        stmt = select(Tag).order_by(Tag.phrase)
        result = await self.session.execute(stmt)
        tags = list(result.scalars().all())

        return tags

    async def create_tag(self, tag_to_create: TagToCreate) -> None:
        async with self.session.begin():
            self.session.add(tag_to_create.tag)
            self.session.add_all(tag_to_create.buttons)

            await self.session.commit()

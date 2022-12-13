from datetime import datetime
from typing import List, Optional
from beanie import PydanticObjectId

from pydantic import BaseModel, Field

class Tag(BaseModel):
    name: str
    content: str
    added_by_tag: str
    added_by_id: int
    added_date: datetime = Field(default_factory=datetime.now)
    use_count: int = 0
    image: Optional[PydanticObjectId] = None
    button_links: List = Field(default_factory=list)

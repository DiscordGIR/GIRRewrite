from datetime import datetime
from typing import List
from beanie import Document
from pydantic import Field

class Giveaway(Document):
    _id: int = Field(default_factory=int)
    is_ended: bool = False
    end_time: datetime
    channel: int
    name: str
    entries: List[int] = Field(default_factory=list)
    previous_winners: List[int] = Field(default_factory=list)
    sponsor: int
    winners: int

    class Settings:
        name = "giveaways"
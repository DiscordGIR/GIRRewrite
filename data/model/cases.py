from typing import List
from beanie import Document
from pydantic import Field
from .case import Case

class Cases(Document):
    _id: int = Field(default_factory=int)
    cases: List[Case] = Field(default_factory=list)

    class Settings:
        name = "cases"
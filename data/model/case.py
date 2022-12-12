from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

class Case(BaseModel):
    _id: int
    _type: str
    date: datetime = Field(default_factory=datetime.now)
    until: Optional[datetime] = None
    mod_id: int
    mod_tag: str
    reason: str
    punishment: str
    lifted: bool = False
    lifted_by_tag: Optional[str] = None
    lifted_by_id: Optional[int] = None
    lifted_reason: Optional[str] = None
    lifted_date: Optional[datetime] = None
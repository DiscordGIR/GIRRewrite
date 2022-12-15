from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

class Case(BaseModel):
    id: int = Field(default_factory=int)
    type: str = Field(alias="_type")
    date: datetime = Field(default_factory=datetime.now)
    until: Optional[datetime] = None
    mod_id: int
    mod_tag: str
    reason: str
    punishment: Optional[str] = None
    lifted: bool = False
    lifted_by_tag: Optional[str] = None
    lifted_by_id: Optional[int] = None
    lifted_reason: Optional[str] = None
    lifted_date: Optional[datetime] = None
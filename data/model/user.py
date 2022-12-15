

from typing import Dict, List, Optional
from beanie import Document
from pydantic import BaseModel, Field


class User(Document):
    id: int = Field(default_factory=int)
    is_clem: bool = False
    is_xp_frozen: bool = False
    is_muted: bool = False
    is_music_banned: bool = False
    was_warn_kicked: bool = False
    birthday_excluded: bool = False
    raid_verified: bool = False
    
    xp: int = 0
    trivia_points: int = 0
    level: int = 0
    warn_points: int = 0

    offline_report_ping: bool = False
    
    timezone: Optional[str] = None
    birthday: List[int] = Field(default_factory=list)
    sticky_roles: List[int] = Field(default_factory=list)
    command_bans: Dict = Field(default_factory=dict)

    class Settings:
        name = "users"

class XpView(BaseModel):
    id: int = Field(default_factory=int, alias="_id")
    xp: int = 0
    level: int = 0
    is_clem: bool = False

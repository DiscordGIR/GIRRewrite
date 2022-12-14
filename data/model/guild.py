from typing import Dict, List
from beanie import Document, Link
from pydantic import BaseModel, Field
from .filterword import FilterWord
from .tag import Tag


class Guild(Document):
    id: int = Field(default_factory=int)
    case_id: int = 1
    reaction_role_mapping: Dict = Field(default_factory=dict)
    role_administrator: int
    role_birthday: int
    role_dev: int
    role_genius: int
    role_member: int
    role_memberone: int
    role_memberedition: int
    role_memberplus: int
    role_memberpro: int
    role_memberultra: int
    role_moderator: int
    role_mute: int
    role_sub_mod: int
    role_sub_news: int
    
    channel_applenews: int
    channel_booster_emoji: int
    channel_botspam: int
    channel_common_issues: int
    channel_development: int
    channel_emoji_log: int
    channel_general: int
    channel_genius_bar: int
    channel_jailbreak: int
    channel_private: int
    channel_public: int
    channel_rules: int
    channel_reaction_roles: int
    channel_reports: int
    channel_subnews: int
    channel_music: int
    
    emoji_logging_webhook: str
    locked_channels: List[int] = Field(default_factory=list)
    filter_excluded_channels: List[int] = Field(default_factory=list)
    filter_excluded_guilds: List[int] = Field(default_factory=list)
    filter_words: List[FilterWord] = Field(default_factory=list)
    raid_phrases: List[FilterWord] = Field(default_factory=list)
    logging_excluded_channels: List[int] = Field(default_factory=list)
    nsa_guild_id: int
    nsa_mapping: Dict = Field(default_factory=dict)
    tags: List[Tag] = Field(default_factory=list)
    memes: List[Tag] = Field(default_factory=list)
    sabbath_mode: bool = False
    ban_today_spam_accounts: bool = False

    class Settings:
        name = "guilds"


class ChannelsView(BaseModel):
    channel_applenews: int
    channel_booster_emoji: int
    channel_botspam: int
    channel_common_issues: int
    channel_development: int
    channel_emoji_log: int
    channel_general: int
    channel_genius_bar: int
    channel_jailbreak: int
    channel_private: int
    channel_public: int
    channel_rules: int
    channel_reaction_roles: int
    channel_reports: int
    channel_subnews: int
    channel_music: int


class RolesView(BaseModel):
    role_administrator: int
    role_birthday: int
    role_dev: int
    role_genius: int
    role_member: int
    role_memberone: int
    role_memberedition: int
    role_memberplus: int
    role_memberpro: int
    role_memberultra: int
    role_moderator: int
    role_mute: int
    role_sub_mod: int
    role_sub_news: int


class RolesAndChannelsView(ChannelsView, RolesView):
    pass


class TagView(BaseModel):
    tags: List[Tag] = Field(default_factory=list)


class MemeView(BaseModel):
    memes: List[Tag] = Field(default_factory=list)


class CaseIdView(BaseModel):
    case_id: int = 1


class MetaProperties(BaseModel):
    sabbath_mode: bool = False
    ban_today_spam_accounts: bool = False
    nsa_guild_id: int
    nsa_mapping: Dict = Field(default_factory=dict)
    emoji_logging_webhook: str
    locked_channels: List[int] = Field(default_factory=list)
    filter_excluded_channels: List[int] = Field(default_factory=list)
    filter_excluded_guilds: List[int] = Field(default_factory=list)
    reaction_role_mapping: Dict = Field(default_factory=dict)
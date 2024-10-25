import datetime
import enum
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, BigInteger, String, Boolean, ForeignKey, Index, PrimaryKeyConstraint, Enum, DateTime, \
    Integer

from contextlib import asynccontextmanager

class Base(DeclarativeBase):
    pass


class GuildSetting(Base):
    __tablename__ = 'guild_setting'

    guild_id = Column(BigInteger, primary_key=True)
    sabbath_mode = Column(Boolean)
    ban_today_spam = Column(Boolean)

    def __repr__(self):
        return '<GuildSetting %r>' % self.guild_id


class User(Base):
    __tablename__ = 'user'

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    is_clem = Column(Boolean, default=False)
    was_warn_kicked = Column(Boolean, default=False)
    is_birthday_banned = Column(Boolean, default=False)
    is_raid_verified = Column(Boolean, default=False)
    warn_points = Column(BigInteger, default=0)
    timezone = Column(String)
    should_offline_report_ping = Column(Boolean, default=False)

    __table_args__ = (
        Index('user_user_id_index', user_id),
    )

    def __repr__(self):
        return f"<User(id={self.user_id}, username={self.username})>"


class UserBirthday(Base):
    __tablename__ = 'user_birthday'

    user_id = Column(BigInteger, ForeignKey('user.user_id'), primary_key=True)
    day = Column(Integer)
    month = Column(Integer)

    __table_args__ = (
        Index('user_birthday_index', month, day),
    )


class StickyRole(Base):
    __tablename__ = 'sticky_role'

    role_id = Column(BigInteger)
    user_id = Column(BigInteger, ForeignKey('user.user_id'))

    __table_args__ = (
        PrimaryKeyConstraint('role_id', 'user_id'),
        Index('sticky_role_user_id_index', user_id),
    )


class UserXp(Base):
    __tablename__ = 'user_xp'

    user_id = Column(BigInteger, ForeignKey('user.user_id'), primary_key=True)
    xp = Column(BigInteger, default=0)
    level = Column(BigInteger, default=0)
    is_xp_frozen = Column(Boolean, default=False)

    __table_args__ = (
        Index('user_xp_user_index', user_id),
    )

    def __repr__(self):
        return f"<UserXp(user_id={self.user_id}, xp={self.xp})>"


class CaseType(enum.Enum):
    BAN = 'BAN'
    KICK = 'KICk'
    MUTE = 'MUTE'
    WARN = 'WARN'
    UNBAN = 'UNBAN'
    UNMUTE = 'UNMUTE'
    LIFTWARN = 'LIFTWARN'
    REMOVEPOINTS = 'REMOVEPOINTS'
    CLEM = 'CLEM'


class Case(Base):
    __tablename__ = 'case'

    case_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    mod_id = Column(BigInteger, nullable=False)
    type = Column(Enum(CaseType), nullable=False)
    punishment = Column(String)
    reason = Column(String)
    date = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    until = Column(DateTime)
    lifted = Column(Boolean, default=False)
    lifted_by_id = Column(BigInteger)
    lifted_reason = Column(String)
    lifted_date = Column(DateTime)

    __table_args__ = (
        Index('case_case_id_index', case_id),
        Index('case_user_id_index', user_id),
    )

    def __repr__(self):
        return f"<Case(case_id={self.case_id}, user_id={self.user_id}), mod_id={self.mod_id}, action={self.action}, reason={self.reason}>"


class Tag(Base):
    __tablename__ = 'tag'

    phrase = Column(String, primary_key=True)
    creator_id = Column(BigInteger, ForeignKey('user.user_id'))
    uses = Column(BigInteger, default=0)
    image = Column(String)
    updated_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    content = Column(String)

    __table_args__ = (
        Index('tag_name_index', phrase),
    )

    def __repr__(self):
        return f"<Tag(name={self.phrase}, owner_id={self.creator_id}, uses={self.uses}>"


class TagButton(Base):
    __tablename__ = 'tag_button'

    button_id = Column(BigInteger, primary_key=True, autoincrement=True)
    tag_name = Column(String, ForeignKey('tag.phrase'), nullable=False)
    label = Column(String, nullable=False)
    link = Column(String, nullable=False)

    __table_args__ = (
        Index('tag_button_tag_name_index', tag_name),
    )


class Meme(Base):
    __tablename__ = 'meme'

    phrase = Column(String, primary_key=True)
    creator_id = Column(BigInteger, ForeignKey('user.user_id'))
    uses = Column(BigInteger, default=0)
    image = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    content = Column(String)

    __table_args__ = (
        Index('meme_name_index', phrase),
    )

    def __repr__(self):
        return f"<Meme(name={self.phrase}, owner_id={self.creator_id}, uses={self.uses}>"



class FilterWord(Base):
    __tablename__ = 'filter_word'

    phrase = Column(String, primary_key=True)
    should_notify = Column(Boolean, nullable=False)
    filter_without_removing = Column(Boolean, default=False)
    bypass_level = Column(BigInteger, nullable=False)
    disable_extra_checks = Column(Boolean, default=False)
    is_piracy_phrase = Column(Boolean, default=False)

    __table_args__ = (
        Index('filter_word_word_index', phrase),
    )


class RaidPhrase(Base):
    __tablename__ = 'raid_phrase'

    phrase = Column(String, primary_key=True)

    __table_args__ = (
        Index('raid_phrase_word_index', phrase),
    )


class LockedChannel(Base):
    __tablename__ = 'locked_channel'

    channel_id = Column(BigInteger, primary_key=True)


class FilterExcludedGuild(Base):
    __tablename__ = 'filter_excluded_guild'

    guild_id = Column(BigInteger, primary_key=True)


class LoggingExcludedChannel(Base):
    __tablename__ = 'logging_excluded_channel'

    channel_id = Column(BigInteger, primary_key=True)

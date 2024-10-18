from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Boolean

class Base(DeclarativeBase):
    pass

class GuildSetting(Base):
    __tablename__ = 'guild_setting'

    guild_id = Column(Integer, primary_key=True)
    sabbath_mode = Column(Boolean)
    ban_today_spam = Column(Boolean)

class User(Base):
    __tablename__ = 'user'

    user_id = Column(Integer, primary_key=True)
    username = Column(String)
    is_clem = Column(Boolean, default=False)
    was_warn_kicked = Column(Boolean, default=False)
    is_birthday_banned = Column(Boolean, default=False)
    is_raid_verified = Column(Boolean, default=False)
    warn_points = Column(Integer, default = 0)
    timezone = Column(String)
    birthday = Column(String)
    should_offline_report_ping = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User(id={self.user_id}, username={self.username})>"

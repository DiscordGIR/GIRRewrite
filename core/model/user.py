from sqlalchemy import Column, BigInteger, String, Boolean

from . import Base


class User(Base):
    __tablename__ = 'user'

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String)
    is_clem = Column(Boolean, default=False)
    xp = Column(BigInteger, default=-1)
    level = Column(BigInteger, default=-1)
    is_xp_frozen = Column(Boolean, default=False)
    was_warn_kicked = Column(Boolean, default=False)
    is_birthday_banned = Column(Boolean, default=False)
    is_raid_verified = Column(Boolean, default=False)
    warn_points = Column(BigInteger, default=-1)
    timezone = Column(String)
    should_offline_report_ping = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User(id={self.user_id}, xp={self.xp}, level={self.level}, warn_points={self.warn_points})>"
import datetime
import enum

from sqlalchemy import Column, BigInteger, String, Boolean, Index, Enum, DateTime

from . import Base


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

    case_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
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

    def __repr__(self):
        return f"<Case(case_id={self.case_id}, user_id={self.user_id}), mod_id={self.mod_id}, punishment={self.punishment}, reason={self.reason}>"

from sqlalchemy import Column, BigInteger, Boolean, ForeignKey, Index

from . import Base


class UserXp(Base):
    __tablename__ = 'user_xp'

    user_id = Column(BigInteger, ForeignKey('user.user_id'), primary_key=True, index=True)
    xp = Column(BigInteger, default=-1)
    level = Column(BigInteger, default=-1)
    is_xp_frozen = Column(Boolean, default=False)

    def __repr__(self):
        return f"<UserXp(user_id={self.user_id}, xp={self.xp})>"

from sqlalchemy import Column, BigInteger, ForeignKey, Integer, Index

from . import Base


class UserBirthday(Base):
    __tablename__ = 'user_birthday'

    user_id = Column(BigInteger, ForeignKey('user.user_id'), primary_key=True)
    day = Column(Integer)
    month = Column(Integer)

    __table_args__ = (
        Index('user_birthday_index', month, day),
    )


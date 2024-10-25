from sqlalchemy import Column, BigInteger, String, Boolean, Index

from . import Base


class LockedChannel(Base):
    __tablename__ = 'locked_channel'

    channel_id = Column(BigInteger, primary_key=True)

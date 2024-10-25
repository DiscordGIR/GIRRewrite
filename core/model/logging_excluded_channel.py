from sqlalchemy import BigInteger, Column

from .import Base


class LoggingExcludedChannel(Base):
    __tablename__ = 'logging_excluded_channel'

    channel_id = Column(BigInteger, primary_key=True)

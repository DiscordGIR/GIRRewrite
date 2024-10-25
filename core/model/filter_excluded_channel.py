from sqlalchemy import Column, BigInteger

from . import Base


class FilterExcludedGuild(Base):
    __tablename__ = 'filter_excluded_guild'

    guild_id = Column(BigInteger, primary_key=True)



from sqlalchemy import Column, String

from . import Base


class RaidPhrase(Base):
    __tablename__ = 'raid_phrase'

    phrase = Column(String, primary_key=True, index=True)

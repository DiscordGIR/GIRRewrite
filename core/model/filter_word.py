from .import Base
from sqlalchemy import Column, BigInteger, String, Boolean, Index, Integer


class FilterWord(Base):
    __tablename__ = 'filter_word'

    phrase = Column(String, primary_key=True, index=True)
    should_notify = Column(Boolean, nullable=False)
    filter_without_removing = Column(Boolean, default=False)
    bypass_level = Column(Integer, nullable=False)
    disable_extra_checks = Column(Boolean, default=False)
    is_piracy_phrase = Column(Boolean, default=False)

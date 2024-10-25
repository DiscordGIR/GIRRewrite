from sqlalchemy import Column, BigInteger, String, Boolean, ForeignKey, Index, DateTime

from .import Base


class TagButton(Base):
    __tablename__ = 'tag_button'

    button_id = Column(BigInteger, primary_key=True, autoincrement=True)
    tag_name = Column(String, ForeignKey('tag.phrase'), nullable=False, index=True)
    label = Column(String, nullable=False)
    link = Column(String, nullable=False)


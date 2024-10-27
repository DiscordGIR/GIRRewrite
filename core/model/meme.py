import datetime

from sqlalchemy import Column, BigInteger, String, ForeignKey, Index, DateTime, Integer

from . import Base


class Meme(Base):
    __tablename__ = 'meme'

    phrase = Column(String, primary_key=True, index=True)
    creator_id = Column(BigInteger, ForeignKey('user.user_id'))
    creator_tag = Column(String)
    uses = Column(Integer, default=-1)
    image = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    content = Column(String)

    def __repr__(self):
        return f"<Meme(name={self.phrase}, owner_id={self.creator_id}, owner_tag={self.creator_tag}, uses={self.uses}>"

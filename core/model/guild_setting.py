from sqlalchemy import Column, BigInteger, Boolean

from . import Base

class GuildSetting(Base):
    __tablename__ = 'guild_setting'

    guild_id = Column(BigInteger, primary_key=True)
    sabbath_mode = Column(Boolean)
    ban_today_spam = Column(Boolean)

    def __repr__(self):
        return '<GuildSetting %r>' % self.guild_id

from sqlalchemy import Column, BigInteger, ForeignKey, PrimaryKeyConstraint, Index

from . import Base


class StickyRole(Base):
    __tablename__ = 'sticky_role'

    role_id = Column(BigInteger)
    user_id = Column(BigInteger, ForeignKey('user.user_id'), index=True)

    __table_args__ = (
        PrimaryKeyConstraint('role_id', 'user_id'),
    )

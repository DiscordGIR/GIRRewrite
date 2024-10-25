import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker



@asynccontextmanager
async def get_session(engine) -> AsyncSession:
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with AsyncSessionLocal() as session:
        yield session
        await session.close()



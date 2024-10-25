import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine


def get_engine() -> AsyncEngine:
    engine = create_async_engine(
        f"postgresql+asyncpg://{os.environ.get('PG_USERNAME')}:{os.environ.get('PG_PASSWORD')}@{os.environ.get('PG_HOST')}:{os.environ.get('PG_PORT')}/{os.environ.get('PG_DATABASE')}",
        echo=True,
        pool_pre_ping=True,
    )

    return engine


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



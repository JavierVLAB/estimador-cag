"""Async SQLAlchemy engine and per-request sessions for the pgvector store."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Create the engine lazily so importing the app never opens a connection."""
    engine = create_async_engine(get_settings().DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one async session per request."""
    async with get_sessionmaker()() as session:
        yield session

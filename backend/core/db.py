from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Dependency для Litestar и прямого использования."""
    async with AsyncSessionFactory() as session:
        yield session

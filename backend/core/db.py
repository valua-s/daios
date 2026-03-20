from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,  # SQL-лог только в dev
    pool_pre_ping=True,               # проверять соединение перед использованием
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,           # объекты живут после commit без refresh
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Dependency для Litestar и прямого использования."""
    async with AsyncSessionFactory() as session:
        yield session

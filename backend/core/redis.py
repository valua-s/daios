from __future__ import annotations

from redis.asyncio import Redis

from backend.core.config import settings


def create_redis() -> Redis:
    """Создаёт Redis-клиент. Вызывается при первой потребности через DI."""
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        username=settings.redis_user,
        password=settings.redis_password,
        decode_responses=True,
    )

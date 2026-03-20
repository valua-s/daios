from __future__ import annotations

from redis.asyncio import Redis

from backend.core.config import settings

redis_client: Redis = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    username=settings.redis_user,
    password=settings.redis_password,
    decode_responses=True,
)


async def get_redis() -> Redis:
    """Dependency для Litestar."""
    return redis_client

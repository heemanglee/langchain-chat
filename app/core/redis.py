"""Redis client lifecycle management."""

import redis.asyncio as redis

from app.core.config import settings

redis_client: redis.Redis | None = None  # type: ignore[type-arg]


async def init_redis() -> redis.Redis:  # type: ignore[type-arg]
    """Initialize the Redis connection."""
    global redis_client  # noqa: PLW0603
    redis_client = redis.from_url(settings.redis.url, decode_responses=True)
    await redis_client.ping()
    return redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global redis_client  # noqa: PLW0603
    if redis_client:
        await redis_client.aclose()
        redis_client = None


def get_redis() -> redis.Redis:  # type: ignore[type-arg]
    """Get the active Redis client."""
    if redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return redis_client

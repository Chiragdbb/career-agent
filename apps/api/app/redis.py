from __future__ import annotations

from redis import Redis

from app.config import Settings, get_settings

_redis_client: Redis | None = None


def init_redis(settings: Settings | None = None) -> Redis:
    """Create and cache the Redis client."""
    global _redis_client

    settings = settings or get_settings()
    _redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    return _redis_client


def get_redis() -> Redis:
    if _redis_client is None:
        return init_redis()
    return _redis_client


def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None

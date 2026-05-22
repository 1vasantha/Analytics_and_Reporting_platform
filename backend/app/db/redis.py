# Async Redis client wrapper- Single connection pool per process for result caching, Rate limiting, Refresh token revocation list, WebSocket pub/sub for cross-worker fanout

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_pool: ConnectionPool | None = None

# Returns a shared Redis connection pool (singleton per app instance)
def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
        )
    return _pool

# Return a Redis client backed by the shared pool.
def get_redis() -> Redis:
    return Redis(connection_pool=get_pool())

# Close the Redis pool. Call on application shutdown.
async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None

# Cache helpers
# Fetch a JSON-serialized value from cache. Returns None if missing
async def cache_get(key: str) -> Any | None:
    redis = get_redis()
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None

# Store a JSON-serializable value with TTL.
async def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    redis = get_redis()
    await redis.set(key, json.dumps(value, default=str), ex=ttl_seconds)

# Delete cache
async def cache_delete(*keys: str) -> int:
    if not keys:
        return 0
    redis = get_redis()
    return await redis.delete(*keys)

# Delete all keys matching a glob pattern. Uses SCAN to avoid blocking.
async def cache_delete_pattern(pattern: str) -> int:
    redis = get_redis()
    deleted = 0
    async for key in redis.scan_iter(match=pattern, count=100):
        deleted += await redis.delete(key)
    return deleted

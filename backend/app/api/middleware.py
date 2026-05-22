"""Sliding-window rate limiter backed by Redis.

Per-IP global limit applied to all endpoints, with overrides for:
  * auth endpoints (tighter — protect against brute force)
  * ingestion endpoints (higher — accommodate burst writes)

Uses Redis sorted set per (key, window). Each request inserts a timestamp;
old entries trimmed; cardinality enforced.
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.exceptions import RateLimitError
from app.db.redis import get_redis


def _key_for(request: Request) -> tuple[str, int]:
    """Pick a Redis key and limit for the current request."""
    ip = request.client.host if request.client else "unknown"
    path = request.url.path

    if path.startswith("/api/v1/auth/login") or path.startswith("/api/v1/auth/register"):
        return f"rl:auth:{ip}", settings.RATE_LIMIT_AUTH_PER_MINUTE
    if path.startswith("/api/v1/ingest"):
        return f"rl:ingest:{ip}", settings.RATE_LIMIT_INGESTION_PER_MINUTE
    return f"rl:global:{ip}", settings.RATE_LIMIT_PER_MINUTE


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply per-IP sliding-window rate limits."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Skip non-API paths (docs, health, websocket handshakes)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        key, limit = _key_for(request)
        window_seconds = 60
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - window_seconds * 1000

        redis = get_redis()
        # Pipeline: remove old + add new + count + expire
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff_ms)
        pipe.zadd(key, {f"{now_ms}-{id(request)}": now_ms})
        pipe.zcard(key)
        pipe.expire(key, window_seconds + 1)
        _, _, count, _ = await pipe.execute()

        if count > limit:
            raise RateLimitError(
                f"Rate limit exceeded ({limit}/min)",
                details={"limit": limit, "window_seconds": window_seconds},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return response

"""Async database engine and session management.

Provides:
- `engine`: module-level async engine (one per process)
- `AsyncSessionLocal`: session factory
- `get_db()`: FastAPI dependency that yields a session and ensures cleanup
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

# In tests we use NullPool to avoid event-loop issues across test boundaries
_is_test = settings.ENVIRONMENT == "development" and settings.POSTGRES_DB.endswith("_test")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE if not _is_test else 5,
    max_overflow=settings.DB_MAX_OVERFLOW if not _is_test else 0,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,  # validates connections before use, handles stale conns
    poolclass=NullPool if _is_test else None,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a request-scoped database session.

    The session is closed automatically when the request completes.
    Exceptions trigger a rollback; commits are explicit in service code.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

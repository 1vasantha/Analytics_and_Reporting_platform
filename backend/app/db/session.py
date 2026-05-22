# Async database engine and session management that provides engine, AsyncSessionLocal,get_db

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
    pool_pre_ping=True,
    poolclass=NullPool if _is_test else None,
)

# session creation per request
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# dependency that provides a request-scoped database session and closed automatically when the request completes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Async database engine and session management that provides engine, AsyncSessionLocal,get_db

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

_engine: Optional[AsyncEngine] = None
_AsyncSessionLocal: Optional[async_sessionmaker] = None

def _is_test_env() -> bool:
    return settings.ENVIRONMENT == "development" and settings.POSTGRES_DB.endswith("_test")

def get_engine() -> AsyncEngine:
    """Get or create the async engine. Lazy — created on first call."""
    global _engine
    if _engine is None:
        is_test = _is_test_env()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DB_ECHO,
            pool_size=settings.DB_POOL_SIZE if not is_test else 5,
            max_overflow=settings.DB_MAX_OVERFLOW if not is_test else 0,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_pre_ping=True,
            poolclass=NullPool if is_test else None,
        )
    return _engine

def get_session_factory() -> async_sessionmaker:
    """Get or create the session factory. Lazy — created on first call."""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _AsyncSessionLocal

# Keep AsyncSessionLocal as a callable for backwards compatibility
# across all your existing code that imports it
class _LazySessionLocal:
    def __call__(self):
        return get_session_factory()()
    
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)

AsyncSessionLocal = _LazySessionLocal()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
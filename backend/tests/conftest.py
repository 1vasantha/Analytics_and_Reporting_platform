# Pytest fixtures for the test suite.

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.session import get_db
from app.main import create_app
from app.models import Base

# Session-scoped event loop so the engine is shared across tests
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# A separate engine pointing at a test database
@pytest_asyncio.fixture(scope="session")
async def test_engine():
    url = settings.DATABASE_URL.replace(
        f"/{settings.POSTGRES_DB}", f"/{settings.POSTGRES_DB}_test"
    )
    engine = create_async_engine(url, poolclass=None)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

# Per-test session — wraps each test in a transaction and rolls back
@pytest_asyncio.fixture
async def db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await test_engine.connect()
    transaction = await connection.begin()
    Session = async_sessionmaker(bind=connection, expire_on_commit=False)

    async with Session() as session:
        yield session

    await transaction.rollback()
    await connection.close()

# HTTP client with DB dependency overridden to the test session
@pytest_asyncio.fixture
async def client(db) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac

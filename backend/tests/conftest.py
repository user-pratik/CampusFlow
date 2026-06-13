"""Test configuration and shared fixtures for CampusFlow tests.

Provides async test client, in-memory SQLite database, and session overrides
for complete test isolation.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app as fastapi_app
from app.database import get_session
import app.models  # noqa: F401 — ensure models registered with metadata

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """Create an in-memory SQLite engine with all tables, torn down after test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Provide a fresh async session bound to the in-memory test database."""
    session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session):
    """Async HTTP client with the get_session dependency overridden for isolation."""

    async def override_get_session():
        yield test_session

    fastapi_app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()

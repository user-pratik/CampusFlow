"""Database layer for CampusFlow.

Async SQLite engine via aiosqlite, session factory, and table initialization.
"""

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


DATABASE_URL = "sqlite+aiosqlite:///./campusflow.db"

engine = create_async_engine(DATABASE_URL, echo=False)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement for SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    """Async generator yielding a database session for FastAPI dependency injection."""
    async with async_session_maker() as session:
        yield session


async def init_db():
    """Create all tables defined in SQLModel metadata."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

"""Tests for CampusFlow database models.

Validates model field existence, types, FK constraints, and table creation.
Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.8
"""

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Digest, Event, Notice, Task

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def fk_engine():
    """In-memory SQLite engine with foreign key enforcement enabled."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Enable FK enforcement for the async SQLite engine via pool events
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def fk_session(fk_engine):
    """Session with FK enforcement for constraint testing."""
    session_maker = async_sessionmaker(
        fk_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session


# ---------- Notice model field tests (Requirement 3.1) ----------


class TestNoticeModel:
    """Tests for the Notice model fields and types."""

    def test_notice_has_required_fields(self):
        """Notice model exposes all required fields."""
        notice = Notice(
            text_hash="abc123",
            source_group="College Group",
            raw_text="Some announcement",
            parsed_title="Announcement",
            category="academic",
            is_processed=False,
            created_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        assert notice.text_hash == "abc123"
        assert notice.source_group == "College Group"
        assert notice.raw_text == "Some announcement"
        assert notice.parsed_title == "Announcement"
        assert notice.category == "academic"
        assert notice.is_processed is False
        assert isinstance(notice.created_at, datetime)

    def test_notice_id_defaults_to_none(self):
        """Notice id is None before insertion (auto-generated PK)."""
        notice = Notice(
            text_hash="hash1",
            source_group="group",
            raw_text="text",
            parsed_title="title",
            category="general",
        )
        assert notice.id is None

    def test_notice_is_processed_defaults_to_false(self):
        """is_processed defaults to False."""
        notice = Notice(
            text_hash="hash2",
            source_group="group",
            raw_text="text",
            parsed_title="title",
            category="general",
        )
        assert notice.is_processed is False


# ---------- Task model field tests (Requirement 3.2) ----------


class TestTaskModel:
    """Tests for the Task model fields and types."""

    def test_task_has_required_fields(self):
        """Task model exposes all required fields."""
        task = Task(
            title="Submit assignment",
            deadline=datetime(2024, 6, 15, 23, 59, 0),
            status="pending",
            related_notice_id=1,
            is_conflict=False,
        )
        assert task.title == "Submit assignment"
        assert isinstance(task.deadline, datetime)
        assert task.status == "pending"
        assert task.related_notice_id == 1
        assert task.is_conflict is False

    def test_task_status_defaults_to_pending(self):
        """Task status defaults to 'pending'."""
        task = Task(title="Test", deadline=datetime(2024, 1, 1))
        assert task.status == "pending"

    def test_task_is_conflict_defaults_to_false(self):
        """Task is_conflict defaults to False."""
        task = Task(title="Test", deadline=datetime(2024, 1, 1))
        assert task.is_conflict is False

    def test_task_related_notice_id_nullable(self):
        """Task related_notice_id can be None."""
        task = Task(title="Standalone", deadline=datetime(2024, 1, 1))
        assert task.related_notice_id is None


# ---------- Event model field tests (Requirement 3.3) ----------


class TestEventModel:
    """Tests for the Event model fields and types."""

    def test_event_has_required_fields(self):
        """Event model exposes all required fields."""
        ev = Event(
            title="Workshop",
            start_time=datetime(2024, 6, 10, 10, 0),
            end_time=datetime(2024, 6, 10, 12, 0),
            location="Room 301",
            related_notice_id=2,
        )
        assert ev.title == "Workshop"
        assert isinstance(ev.start_time, datetime)
        assert isinstance(ev.end_time, datetime)
        assert ev.location == "Room 301"
        assert ev.related_notice_id == 2

    def test_event_related_notice_id_nullable(self):
        """Event related_notice_id can be None."""
        ev = Event(
            title="Open session",
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 10, 0),
            location="Auditorium",
        )
        assert ev.related_notice_id is None


# ---------- Digest model field tests (Requirement 3.4) ----------


class TestDigestModel:
    """Tests for the Digest model fields and types."""

    def test_digest_has_required_fields(self):
        """Digest model exposes all required fields."""
        digest = Digest(
            content="Today's summary...",
            generated_at=datetime(2024, 6, 1, 8, 0),
        )
        assert digest.content == "Today's summary..."
        assert isinstance(digest.generated_at, datetime)

    def test_digest_generated_at_has_default(self):
        """Digest generated_at gets a default datetime if not supplied."""
        digest = Digest(content="Auto-timestamp test")
        assert digest.generated_at is not None
        assert isinstance(digest.generated_at, datetime)


# ---------- FK constraint tests (Requirement 3.6) ----------


class TestForeignKeyConstraints:
    """Tests for FK constraints on Task and Event models."""

    @pytest.mark.asyncio
    async def test_task_valid_fk_reference(self, fk_session: AsyncSession):
        """Task with a valid related_notice_id can be inserted."""
        notice = Notice(
            text_hash="fk_test_hash",
            source_group="Test Group",
            raw_text="FK test notice",
            parsed_title="FK Test",
            category="test",
        )
        fk_session.add(notice)
        await fk_session.commit()
        await fk_session.refresh(notice)

        task = Task(
            title="FK linked task",
            deadline=datetime(2024, 12, 31),
            related_notice_id=notice.id,
        )
        fk_session.add(task)
        await fk_session.commit()
        await fk_session.refresh(task)
        assert task.related_notice_id == notice.id

    @pytest.mark.asyncio
    async def test_task_invalid_fk_raises_integrity_error(self, fk_session: AsyncSession):
        """Task with a non-existent related_notice_id raises IntegrityError."""
        task = Task(
            title="Orphan task",
            deadline=datetime(2024, 12, 31),
            related_notice_id=9999,
        )
        fk_session.add(task)
        with pytest.raises(IntegrityError):
            await fk_session.commit()

    @pytest.mark.asyncio
    async def test_event_valid_fk_reference(self, fk_session: AsyncSession):
        """Event with a valid related_notice_id can be inserted."""
        notice = Notice(
            text_hash="ev_fk_hash",
            source_group="Event Group",
            raw_text="Event FK notice",
            parsed_title="Event FK",
            category="event",
        )
        fk_session.add(notice)
        await fk_session.commit()
        await fk_session.refresh(notice)

        ev = Event(
            title="FK linked event",
            start_time=datetime(2024, 6, 1, 10, 0),
            end_time=datetime(2024, 6, 1, 11, 0),
            location="Lab",
            related_notice_id=notice.id,
        )
        fk_session.add(ev)
        await fk_session.commit()
        await fk_session.refresh(ev)
        assert ev.related_notice_id == notice.id

    @pytest.mark.asyncio
    async def test_event_invalid_fk_raises_integrity_error(self, fk_session: AsyncSession):
        """Event with a non-existent related_notice_id raises IntegrityError."""
        ev = Event(
            title="Orphan event",
            start_time=datetime(2024, 6, 1, 10, 0),
            end_time=datetime(2024, 6, 1, 11, 0),
            location="Nowhere",
            related_notice_id=9999,
        )
        fk_session.add(ev)
        with pytest.raises(IntegrityError):
            await fk_session.commit()


# ---------- Table creation tests (Requirement 3.8) ----------


class TestTableCreation:
    """Tests verifying tables are created correctly via metadata."""

    @pytest.mark.asyncio
    async def test_all_tables_exist(self, test_engine):
        """All four tables (notices, tasks, events, digests) are created."""
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result.fetchall()}

        assert "notices" in tables
        assert "tasks" in tables
        assert "events" in tables
        assert "digests" in tables

    @pytest.mark.asyncio
    async def test_notices_table_columns(self, test_engine):
        """Notices table has the expected columns."""
        async with test_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(notices)"))
            columns = {row[1] for row in result.fetchall()}

        expected = {
            "id", "text_hash", "source_group", "raw_text",
            "parsed_title", "category", "is_processed", "created_at",
        }
        assert expected.issubset(columns)

    @pytest.mark.asyncio
    async def test_tasks_table_columns(self, test_engine):
        """Tasks table has the expected columns."""
        async with test_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(tasks)"))
            columns = {row[1] for row in result.fetchall()}

        expected = {
            "id", "title", "deadline", "status",
            "related_notice_id", "is_conflict",
        }
        assert expected.issubset(columns)

    @pytest.mark.asyncio
    async def test_events_table_columns(self, test_engine):
        """Events table has the expected columns."""
        async with test_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(events)"))
            columns = {row[1] for row in result.fetchall()}

        expected = {
            "id", "title", "start_time", "end_time",
            "location", "related_notice_id",
        }
        assert expected.issubset(columns)

    @pytest.mark.asyncio
    async def test_digests_table_columns(self, test_engine):
        """Digests table has the expected columns."""
        async with test_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(digests)"))
            columns = {row[1] for row in result.fetchall()}

        expected = {"id", "content", "generated_at"}
        assert expected.issubset(columns)

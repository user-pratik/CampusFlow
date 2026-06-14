"""Property-based test for data persistence replacement correctness.

Feature: embedded-vtop-login, Property 9: Data persistence replacement correctness

Validates: Requirements 6.3

For any non-empty set of attendance/marks records, after the SyncOrchestrator
persists them, the database SHALL contain exactly those records (no records from
prior syncs) with matching field values.

Since Hypothesis tests cannot easily use async pytest fixtures, we validate
the replacement property structurally by mocking async_session_maker and
verifying that:
  1. delete() is called (to wipe prior data)
  2. Exactly N records are added via session.add()
  3. commit() is called exactly once (atomic replacement)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

from hypothesis import given, settings
from hypothesis.strategies import integers, text, composite, lists, floats

from app.connectors.vtop.sync_orchestrator import SyncOrchestrator


@composite
def attendance_records(draw):
    """Generate a non-empty list of attendance record dicts."""
    n = draw(integers(min_value=1, max_value=5))
    records = []
    for _ in range(n):
        total = draw(integers(min_value=1, max_value=50))
        attended = draw(integers(min_value=0, max_value=total))
        records.append({
            "course_code": draw(text(alphabet="ABCDEFGHIJKLMNOP0123456789", min_size=6, max_size=8)),
            "course_title": draw(text(alphabet="abcdefghijklmnop ", min_size=5, max_size=20)),
            "attended": attended,
            "total": total,
            "percentage": draw(floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
        })
    return records


@composite
def marks_records(draw):
    """Generate a non-empty list of marks record dicts."""
    n = draw(integers(min_value=1, max_value=5))
    records = []
    for _ in range(n):
        records.append({
            "course_code": draw(text(alphabet="ABCDEFGHIJKLMNOP0123456789", min_size=6, max_size=8)),
            "course_title": draw(text(alphabet="abcdefghijklmnop ", min_size=5, max_size=20)),
            "mark_title": draw(text(alphabet="abcdefghijklmnop 0123456789", min_size=3, max_size=15)),
            "max_mark": draw(floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
            "weightage_pct": draw(floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
            "score": draw(floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
            "weightage_mark": draw(floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
            "status": draw(text(alphabet="PresentAbsent", min_size=6, max_size=7)),
        })
    return records


def _make_mock_session():
    """Create a mock async session that tracks add/delete/commit calls."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.exec = AsyncMock()
    mock_session.commit = AsyncMock()

    # Make it work as an async context manager
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


@settings(max_examples=100)
@given(records=attendance_records())
def test_persist_attendance_replaces_existing(records):
    """For any non-empty set of attendance records, _persist_attendance SHALL
    delete all existing records and insert exactly the new records atomically.

    Verifies:
    - delete() is called (replacement semantics)
    - session.add() is called exactly len(records) times
    - commit() is called exactly once (atomicity)

    **Validates: Requirements 6.3**
    """
    mock_session = _make_mock_session()
    mock_session_maker = MagicMock(return_value=mock_session)

    orchestrator = SyncOrchestrator(AsyncMock())

    with patch("app.connectors.vtop.sync_orchestrator.async_session_maker", mock_session_maker):
        asyncio.run(orchestrator._persist_attendance(records))

    # Verify delete was called (replacement — wipe old data)
    mock_session.exec.assert_called_once()

    # Verify exactly N records were added
    assert mock_session.add.call_count == len(records)

    # Verify commit was called exactly once (atomic transaction)
    mock_session.commit.assert_called_once()


@settings(max_examples=100)
@given(records=marks_records())
def test_persist_marks_replaces_existing(records):
    """For any non-empty set of marks records, _persist_marks SHALL
    delete all existing records and insert exactly the new records atomically.

    Verifies:
    - delete() is called (replacement semantics)
    - session.add() is called exactly len(records) times
    - commit() is called exactly once (atomicity)

    **Validates: Requirements 6.3**
    """
    mock_session = _make_mock_session()
    mock_session_maker = MagicMock(return_value=mock_session)

    orchestrator = SyncOrchestrator(AsyncMock())

    with patch("app.connectors.vtop.sync_orchestrator.async_session_maker", mock_session_maker):
        asyncio.run(orchestrator._persist_marks(records))

    # Verify delete was called (replacement — wipe old data)
    mock_session.exec.assert_called_once()

    # Verify exactly N records were added
    assert mock_session.add.call_count == len(records)

    # Verify commit was called exactly once (atomic transaction)
    mock_session.commit.assert_called_once()

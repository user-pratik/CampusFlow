"""SchedulerAgent — Inserts extracted data into DB with conflict detection."""

from datetime import datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.base import BaseAgent
from app.database import async_session_maker
from app.models import Event, Notice, Task
from app.utils.hashing import compute_text_hash


class SchedulerAgent(BaseAgent):
    """Takes structured extraction output and persists it to the database.

    Handles:
    - Notice record insertion
    - Event creation (if is_calendar_event)
    - Task creation with ±1 hour conflict detection (if is_actionable_task)
    """

    async def execute(self, payload: dict) -> dict:
        """Insert extracted notice data into the database.

        Args:
            payload: Dict containing NoticeExtraction fields plus
                     'raw_text' and 'source_group'.

        Returns:
            Dict summarizing what was inserted (notice_id, event_id, task_id,
            is_conflict).
        """
        async with async_session_maker() as session:
            result = await self._process(session, payload)
            await session.commit()
        return result

    async def _process(self, session: AsyncSession, payload: dict) -> dict:
        """Core processing logic within a session transaction."""

        # 1. Insert Notice record
        text_hash = compute_text_hash(payload["raw_text"])
        notice = Notice(
            text_hash=text_hash,
            source_group=payload["source_group"],
            raw_text=payload["raw_text"],
            parsed_title=payload["parsed_title"],
            category=payload["category"],
            is_processed=True,
        )
        session.add(notice)
        await session.flush()  # Populate notice.id

        result: dict = {
            "notice_id": notice.id,
            "event_id": None,
            "task_id": None,
            "is_conflict": False,
        }

        # 2. Insert Event if is_calendar_event
        if payload.get("is_calendar_event") and payload.get("start_time"):
            event = Event(
                title=payload["parsed_title"],
                start_time=_parse_dt(payload["start_time"]),
                end_time=_parse_dt(payload["end_time"]) if payload.get("end_time") else _parse_dt(payload["start_time"]),
                location=payload.get("location") or "TBD",
                related_notice_id=notice.id,
            )
            session.add(event)
            await session.flush()
            result["event_id"] = event.id

        # 3. Insert Task if is_actionable_task
        if payload.get("is_actionable_task") and payload.get("deadline"):
            deadline = _parse_dt(payload["deadline"])
            is_conflict = await self._check_conflict(
                session, payload["category"], deadline
            )
            task = Task(
                title=payload["parsed_title"],
                deadline=deadline,
                status="pending",
                related_notice_id=notice.id,
                is_conflict=is_conflict,
            )
            session.add(task)
            await session.flush()
            result["task_id"] = task.id
            result["is_conflict"] = is_conflict

        return result

    async def _check_conflict(
        self, session: AsyncSession, category: str, deadline: datetime
    ) -> bool:
        """Check if a task with the same category exists within ±1 hour of deadline.

        Returns True if a conflict is detected.
        """
        window_start = deadline - timedelta(hours=1)
        window_end = deadline + timedelta(hours=1)

        statement = select(Task).where(
            Task.deadline >= window_start,
            Task.deadline <= window_end,
        )
        existing = await session.exec(statement)
        tasks_in_window = existing.all()

        # Check if any share the same category
        for task in tasks_in_window:
            # Match category from the linked notice
            notice_result = await session.exec(
                select(Notice).where(Notice.id == task.related_notice_id)
            )
            linked_notice = notice_result.first()
            if linked_notice and linked_notice.category == category:
                return True

        return False


def _parse_dt(value) -> datetime:
    """Parse a datetime from string or pass through if already datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle ISO format strings from JSON
        return datetime.fromisoformat(value)
    raise ValueError(f"Cannot parse datetime from: {value!r}")

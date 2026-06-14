"""Deadlines router — sync and timeline endpoints."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Deadline

router = APIRouter()


@router.post("/deadlines/sync")
async def sync_deadlines():
    """Run deadline extraction from all sources (Gmail + manual calendar + Moodle).

    Scans EmailNotification records, manual data files, and Moodle assignments,
    extracts deadlines via LLM/parsing/API, and upserts to the Deadline table.
    """
    from app.agents.deadline_aggregator import (
        extract_deadlines_from_emails,
        fetch_moodle_deadlines,
        load_manual_deadlines,
    )

    gmail_results = await extract_deadlines_from_emails()
    manual_results = await load_manual_deadlines()
    moodle_results = await fetch_moodle_deadlines()

    return {
        "status": "completed",
        "gmail_deadlines": len(gmail_results),
        "manual_deadlines": len(manual_results),
        "moodle_deadlines": len(moodle_results),
        "total_new": len(gmail_results) + len(manual_results) + len(moodle_results),
        "details": {
            "gmail": gmail_results,
            "manual": manual_results,
            "moodle": moodle_results,
        },
    }


@router.get("/deadlines/timeline")
async def get_deadline_timeline(session: AsyncSession = Depends(get_session)):
    """Return upcoming deadlines grouped by week, soonest first.

    Response format:
    {
        "weeks": [
            {
                "label": "This Week (Jun 16–22)",
                "deadlines": [ ... ]
            },
            ...
        ],
        "total": 12
    }
    """
    now = datetime.utcnow()

    # Fetch upcoming deadlines (not missed/completed), ordered by due date
    result = await session.exec(
        select(Deadline)
        .where(Deadline.status == "upcoming")
        .where(Deadline.due_datetime >= now)
        .order_by(Deadline.due_datetime)
    )
    deadlines = result.all()

    # Group by ISO week
    weeks: list[dict] = []
    current_week_start: datetime | None = None
    current_week_deadlines: list[dict] = []

    for d in deadlines:
        # Calculate week start (Monday)
        week_start = d.due_datetime - timedelta(days=d.due_datetime.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        if current_week_start is None or week_start != current_week_start:
            # Save previous week if any
            if current_week_deadlines:
                weeks.append({
                    "label": _week_label(current_week_start, now),
                    "week_start": current_week_start.isoformat(),
                    "deadlines": current_week_deadlines,
                })
            current_week_start = week_start
            current_week_deadlines = []

        current_week_deadlines.append({
            "id": d.id,
            "title": d.title,
            "due_datetime": d.due_datetime.isoformat(),
            "category": d.category,
            "source": d.source,
            "status": d.status,
            "days_until": (d.due_datetime - now).days,
        })

    # Don't forget the last week
    if current_week_deadlines and current_week_start:
        weeks.append({
            "label": _week_label(current_week_start, now),
            "week_start": current_week_start.isoformat(),
            "deadlines": current_week_deadlines,
        })

    return {
        "weeks": weeks,
        "total": len(deadlines),
    }


def _week_label(week_start: datetime, now: datetime) -> str:
    """Generate a human-readable week label."""
    this_week_start = now - timedelta(days=now.weekday())
    this_week_start = this_week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    diff_days = (week_start - this_week_start).days

    week_end = week_start + timedelta(days=6)
    date_range = f"{week_start.strftime('%b %d')}–{week_end.strftime('%d')}"

    if diff_days == 0:
        return f"This Week ({date_range})"
    elif diff_days == 7:
        return f"Next Week ({date_range})"
    elif diff_days < 0:
        return f"Overdue ({date_range})"
    else:
        weeks_out = diff_days // 7
        return f"In {weeks_out} week{'s' if weeks_out > 1 else ''} ({date_range})"


@router.patch("/deadlines/{deadline_id}")
async def update_deadline(
    deadline_id: int,
    session: AsyncSession = Depends(get_session),
    status: str = "completed",
):
    """Update a deadline's status (e.g. mark as completed).

    Query params:
        status: new status value (default: "completed")
    """
    result = await session.exec(
        select(Deadline).where(Deadline.id == deadline_id)
    )
    deadline = result.first()

    if deadline is None:
        return {"error": "Deadline not found", "id": deadline_id}

    deadline.status = status
    session.add(deadline)
    await session.commit()

    return {"status": "ok", "id": deadline_id, "new_status": status}

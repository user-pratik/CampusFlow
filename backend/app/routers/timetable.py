"""Timetable router — serves timetable slots grouped by day."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import TimetableSlot

router = APIRouter()

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

WINDOW_START = "08:00"
WINDOW_END = "18:00"


def compute_free_slots(
    slots: list[TimetableSlot],
    window_start: str = WINDOW_START,
    window_end: str = WINDOW_END,
) -> list[dict]:
    """Compute gaps between consecutive classes within a time window.

    Args:
        slots: TimetableSlot records for a single day, need not be sorted.
        window_start: Start of the day window (HH:MM).
        window_end: End of the day window (HH:MM).

    Returns:
        List of dicts with start_time, end_time, duration_minutes.
    """
    # Sort by start_time
    sorted_slots = sorted(slots, key=lambda s: s.start_time)

    # Collect occupied intervals as (start, end) strings
    occupied: list[tuple[str, str]] = []
    for slot in sorted_slots:
        start = slot.start_time or ""
        end = slot.end_time or ""
        if start and end:
            occupied.append((start, end))

    # Merge overlapping intervals
    merged: list[tuple[str, str]] = []
    for start, end in occupied:
        if merged and start <= merged[-1][1]:
            # Overlapping or adjacent — extend
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Find gaps between window_start and window_end
    free: list[dict] = []
    cursor = window_start

    for start, end in merged:
        if start > cursor:
            gap_minutes = _minutes_between(cursor, start)
            if gap_minutes > 0:
                free.append({
                    "start_time": cursor,
                    "end_time": start,
                    "duration_minutes": gap_minutes,
                })
        # Advance cursor past this class
        if end > cursor:
            cursor = end

    # Trailing gap until window end
    if cursor < window_end:
        gap_minutes = _minutes_between(cursor, window_end)
        if gap_minutes > 0:
            free.append({
                "start_time": cursor,
                "end_time": window_end,
                "duration_minutes": gap_minutes,
            })

    return free


def _minutes_between(t1: str, t2: str) -> int:
    """Calculate minutes between two HH:MM strings."""
    h1, m1 = map(int, t1.split(":"))
    h2, m2 = map(int, t2.split(":"))
    return (h2 * 60 + m2) - (h1 * 60 + m1)


@router.get("/timetable")
async def get_timetable(session: AsyncSession = Depends(get_session)):
    """Return all timetable slots grouped by day_of_week.

    Response format:
    {
        "Monday": [ {slot}, {slot}, ... ],
        "Tuesday": [ ... ],
        ...
    }
    """
    result = await session.exec(
        select(TimetableSlot).order_by(TimetableSlot.day_of_week, TimetableSlot.start_time)
    )
    slots = result.all()

    grouped: dict[str, list[dict]] = {}
    for day in DAY_ORDER:
        day_slots = [
            {
                "id": slot.id,
                "course_code": slot.course_code,
                "course_name": slot.course_name,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "slot_type": slot.slot_type,
                "venue": slot.venue,
            }
            for slot in slots
            if slot.day_of_week == day
        ]
        if day_slots:
            grouped[day] = day_slots

    return grouped


@router.get("/timetable/free-slots")
async def get_free_slots(
    day: str = Query(default="today", description="Day of week (e.g. Monday) or 'today'"),
    session: AsyncSession = Depends(get_session),
):
    """Return free time gaps between classes for a given day within 8am-6pm.

    Query params:
        day: "today" (default) or a day name like "Monday", "Tuesday", etc.

    Response:
        List of {start_time, end_time, duration_minutes}
    """
    if day.lower() == "today":
        day_name = datetime.now().strftime("%A")
    else:
        # Normalize: capitalize first letter
        day_name = day.strip().capitalize()

    # Validate
    if day_name not in DAY_ORDER:
        return {"error": f"Invalid day: '{day}'. Use a day name (Monday-Sunday) or 'today'."}

    result = await session.exec(
        select(TimetableSlot).where(TimetableSlot.day_of_week == day_name)
    )
    slots = result.all()

    free = compute_free_slots(slots)

    return {
        "day": day_name,
        "free_slots": free,
        "total_free_minutes": sum(s["duration_minutes"] for s in free),
    }

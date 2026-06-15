"""Academic data router — serves attendance, marks, profile, and VTOP sync controls."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import AcademicProfile, Attendance, CourseMark, TimetableSlot

router = APIRouter()


@router.get("/academic/attendance", response_model=list[Attendance])
async def get_attendance(session: AsyncSession = Depends(get_session)):
    """Return all attendance records."""
    result = await session.exec(select(Attendance).order_by(Attendance.course_code))
    return result.all()


@router.get("/academic/marks", response_model=list[CourseMark])
async def get_marks(session: AsyncSession = Depends(get_session)):
    """Return all individual mark entries (grouped by course on frontend)."""
    result = await session.exec(
        select(CourseMark).order_by(CourseMark.course_code, CourseMark.id)
    )
    return result.all()


@router.get("/academic/profile", response_model=AcademicProfile | dict)
async def get_academic_profile(session: AsyncSession = Depends(get_session)):
    """Return the academic profile (CGPA, credits, overall attendance)."""
    result = await session.exec(
        select(AcademicProfile).order_by(AcademicProfile.updated_at.desc()).limit(1)
    )
    profile = result.first()
    if profile is None:
        return {"message": "No academic profile available. Sync VTOP first."}
    return profile


class SyncRequest(BaseModel):
    semester_id: str | None = None


@router.post("/academic/sync")
async def trigger_vtop_sync(body: SyncRequest | None = None):
    """Trigger VTOP data sync using stored session cookies via SyncOrchestrator."""
    from app.connectors.vtop.session_store import SessionStore
    from app.connectors.vtop.sync_orchestrator import SyncOrchestrator

    session_store = SessionStore()
    orchestrator = SyncOrchestrator(session_store)
    try:
        result = await orchestrator.sync_all(body.semester_id if body and body.semester_id else "")
        return result.model_dump()
    finally:
        await orchestrator.close()


@router.post("/academic/login")
async def launch_vtop_login():
    """Deprecated: Use the embedded login modal instead."""
    return {"status": "deprecated", "message": "Use the embedded login modal at /api/vtop/proxy/login"}


@router.post("/academic/full-sync")
async def full_sync():
    """Deprecated: Use /api/vtop/sync instead. Kept for backward compatibility."""
    return {
        "status": "deprecated",
        "message": "Use the new embedded login flow: POST /api/vtop/sync",
        "vtop_login": "deprecated",
        "vtop_sync": "deprecated",
        "whatsapp": "skipped",
    }


@router.get("/academic/semesters")
async def get_available_semesters():
    """Get available VTOP semesters using stored session cookies."""
    from app.connectors.vtop.session_store import SessionStore
    from app.connectors.vtop.sync_orchestrator import SyncOrchestrator

    session_store = SessionStore()
    orchestrator = SyncOrchestrator(session_store)
    try:
        semesters = await orchestrator.get_semesters()
        return {"semesters": semesters}
    finally:
        await orchestrator.close()


@router.get("/attendance/risk")
async def get_attendance_risk(session: AsyncSession = Depends(get_session)):
    """Compute attendance risk per course from stored Attendance data."""
    from app.agents.attendance_risk_agent import calculate_risk

    result = await session.exec(select(Attendance).order_by(Attendance.course_code))
    records = result.all()

    if not records:
        return {"message": "No attendance data. Sync VTOP first.", "risks": []}

    # Deduplicate by course_code — keep the record with lowest attendance %
    seen: dict = {}
    for rec in records:
        code = rec.course_code
        if code not in seen or rec.percentage < seen[code].percentage:
            seen[code] = rec
    deduped = list(seen.values())

    risks = [
        calculate_risk(
            course_code=rec.course_code,
            course_title=rec.course_title,
            attended=rec.attended,
            total=rec.total,
        )
        for rec in deduped
    ]

    return {
        "risks": [r.model_dump() for r in risks],
        "summary": {
            "total_courses": len(risks),
            "critical": sum(1 for r in risks if r.risk_level == "critical"),
            "warning": sum(1 for r in risks if r.risk_level == "warning"),
            "safe": sum(1 for r in risks if r.risk_level == "safe"),
        },
    }


@router.get("/academic/projection")
async def get_cgpa_projection(
    course: str = Query(..., description="Course code (e.g. BCSE302L)"),
    grade: str = Query(..., description="Expected grade (S/A/B/C/D/E/F)"),
    credits: int = Query(default=3, description="Course credit weight"),
    session: AsyncSession = Depends(get_session),
):
    """Project new CGPA if a specific grade is achieved in one course."""
    from app.agents.gpa_projection_agent import VALID_GRADES, project_cgpa

    grade_upper = grade.upper().strip()
    if grade_upper not in VALID_GRADES:
        return {"error": f"Invalid grade '{grade}'. Valid: {VALID_GRADES}"}

    result = await session.exec(
        select(AcademicProfile).order_by(AcademicProfile.updated_at.desc()).limit(1)
    )
    profile = result.first()

    if profile is None:
        return {"error": "No academic profile found. Sync VTOP first."}

    projection = project_cgpa(
        current_cgpa=profile.cgpa,
        current_credits=profile.total_credits,
        course_code=course.upper().strip(),
        expected_grade=grade_upper,
        course_credits=credits,
    )

    return projection.model_dump()


@router.get("/academic/required-grade")
async def get_required_grades(
    target_cgpa: float = Query(..., description="Desired CGPA target (e.g. 8.5)"),
    session: AsyncSession = Depends(get_session),
):
    """Determine what grades are needed in current-semester courses to reach target CGPA."""
    from app.agents.gpa_projection_agent import compute_required_grades

    result = await session.exec(
        select(AcademicProfile).order_by(AcademicProfile.updated_at.desc()).limit(1)
    )
    profile = result.first()

    if profile is None:
        return {"error": "No academic profile found. Sync VTOP first."}

    if target_cgpa < 0 or target_cgpa > 10:
        return {"error": "Target CGPA must be between 0 and 10."}

    marks_result = await session.exec(select(CourseMark))
    all_marks = marks_result.all()

    seen: dict[str, dict] = {}
    for mark in all_marks:
        if mark.course_code not in seen:
            seen[mark.course_code] = {
                "course_code": mark.course_code,
                "credits": 3,
            }

    remaining_courses = list(seen.values())

    if not remaining_courses:
        return {"error": "No course marks found for current semester. Sync VTOP first."}

    result_data = compute_required_grades(
        current_cgpa=profile.cgpa,
        current_credits=profile.total_credits,
        target_cgpa=target_cgpa,
        remaining_courses=remaining_courses,
    )

    return result_data.model_dump()


@router.get("/academic/timetable")
async def get_timetable(session: AsyncSession = Depends(get_session)):
    """Return the student's weekly timetable."""
    result = await session.exec(select(TimetableSlot).order_by(TimetableSlot.day, TimetableSlot.slot))
    slots = result.all()
    if not slots:
        return {"message": "No timetable data. Sync VTOP to load."}

    from collections import defaultdict
    by_day = defaultdict(list)
    for slot in slots:
        by_day[slot.day].append({
            "slot": slot.slot,
            "course_code": slot.course_code,
            "course_type": slot.course_type,
            "venue": slot.venue,
        })

    return {"timetable": dict(by_day)}


# ─── VIT Slot-to-Day/Time Mapping ─────────────────────────────────────────────
# VIT Chennai 2025-26 comprehensive slot timing
# Theory slots span multiple days per week (each slot has 2-3 sessions/week).
# Lab slots are 2-period blocks on a single day.

VIT_PERIOD_TIMES = {
    1:  ("08:00", "08:50"),
    2:  ("09:00", "09:50"),
    3:  ("10:00", "10:50"),
    4:  ("11:00", "11:50"),
    5:  ("12:00", "12:50"),
    6:  ("14:00", "14:50"),
    7:  ("15:00", "15:50"),
    8:  ("16:00", "16:50"),
    9:  ("17:00", "17:50"),
    10: ("18:00", "18:50"),
    11: ("19:00", "19:50"),
}

VIT_SLOT_TIMING = {
    # Morning theory slots (Odd-numbered: A1, B1, etc.)
    "A1": {"periods": [1, 2], "days": ["Monday", "Wednesday", "Friday"]},
    "B1": {"periods": [3, 4], "days": ["Monday", "Wednesday", "Friday"]},
    "C1": {"periods": [5, 6], "days": ["Monday", "Wednesday", "Friday"]},
    "D1": {"periods": [1, 2], "days": ["Tuesday", "Thursday", "Saturday"]},
    "E1": {"periods": [3, 4], "days": ["Tuesday", "Thursday", "Saturday"]},
    "F1": {"periods": [5, 6], "days": ["Tuesday", "Thursday", "Saturday"]},
    "G1": {"periods": [7], "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]},
    # Afternoon theory slots (Even-numbered: A2, B2, etc.)
    "A2": {"periods": [6, 7], "days": ["Monday", "Wednesday", "Friday"]},
    "B2": {"periods": [8, 9], "days": ["Monday", "Wednesday", "Friday"]},
    "C2": {"periods": [10], "days": ["Monday", "Wednesday", "Friday"]},
    "D2": {"periods": [6, 7], "days": ["Tuesday", "Thursday", "Saturday"]},
    "E2": {"periods": [8, 9], "days": ["Tuesday", "Thursday", "Saturday"]},
    "F2": {"periods": [10], "days": ["Tuesday", "Thursday", "Saturday"]},
    "G2": {"periods": [11], "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]},
    # Tutorial slots — single period, same days as parent
    "TA1": {"periods": [1], "days": ["Monday", "Wednesday", "Friday"]},
    "TA2": {"periods": [6], "days": ["Monday", "Wednesday", "Friday"]},
    "TB1": {"periods": [3], "days": ["Monday", "Wednesday", "Friday"]},
    "TB2": {"periods": [8], "days": ["Monday", "Wednesday", "Friday"]},
    "TC1": {"periods": [5], "days": ["Monday", "Wednesday", "Friday"]},
    "TC2": {"periods": [10], "days": ["Monday", "Wednesday", "Friday"]},
    "TD1": {"periods": [1], "days": ["Tuesday", "Thursday", "Saturday"]},
    "TD2": {"periods": [6], "days": ["Tuesday", "Thursday", "Saturday"]},
    "TE1": {"periods": [3], "days": ["Tuesday", "Thursday", "Saturday"]},
    "TE2": {"periods": [8], "days": ["Tuesday", "Thursday", "Saturday"]},
    "TF1": {"periods": [5], "days": ["Tuesday", "Thursday", "Saturday"]},
    "TF2": {"periods": [10], "days": ["Tuesday", "Thursday", "Saturday"]},
    "TG1": {"periods": [7], "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]},
    "TG2": {"periods": [11], "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]},
    "TAA1": {"periods": [2], "days": ["Monday", "Wednesday", "Friday"]},
    # Lab slots (2-period blocks on a single day)
    "L1":  {"periods": [1, 2], "days": ["Monday"]},
    "L2":  {"periods": [1, 2], "days": ["Monday"]},
    "L3":  {"periods": [3, 4], "days": ["Monday"]},
    "L4":  {"periods": [3, 4], "days": ["Monday"]},
    "L5":  {"periods": [5, 6], "days": ["Monday"]},
    "L6":  {"periods": [5, 6], "days": ["Monday"]},
    "L7":  {"periods": [1, 2], "days": ["Tuesday"]},
    "L8":  {"periods": [1, 2], "days": ["Tuesday"]},
    "L9":  {"periods": [3, 4], "days": ["Tuesday"]},
    "L10": {"periods": [3, 4], "days": ["Tuesday"]},
    "L11": {"periods": [5, 6], "days": ["Tuesday"]},
    "L12": {"periods": [5, 6], "days": ["Tuesday"]},
    "L13": {"periods": [1, 2], "days": ["Wednesday"]},
    "L14": {"periods": [1, 2], "days": ["Wednesday"]},
    "L15": {"periods": [3, 4], "days": ["Wednesday"]},
    "L16": {"periods": [3, 4], "days": ["Wednesday"]},
    "L17": {"periods": [5, 6], "days": ["Wednesday"]},
    "L18": {"periods": [5, 6], "days": ["Wednesday"]},
    "L19": {"periods": [1, 2], "days": ["Thursday"]},
    "L20": {"periods": [1, 2], "days": ["Thursday"]},
    "L21": {"periods": [3, 4], "days": ["Thursday"]},
    "L22": {"periods": [3, 4], "days": ["Thursday"]},
    "L23": {"periods": [5, 6], "days": ["Thursday"]},
    "L24": {"periods": [5, 6], "days": ["Thursday"]},
    "L25": {"periods": [1, 2], "days": ["Friday"]},
    "L26": {"periods": [1, 2], "days": ["Friday"]},
    "L27": {"periods": [3, 4], "days": ["Friday"]},
    "L28": {"periods": [3, 4], "days": ["Friday"]},
    "L29": {"periods": [5, 6], "days": ["Friday"]},
    "L30": {"periods": [5, 6], "days": ["Friday"]},
    "L31": {"periods": [7, 8], "days": ["Monday"]},
    "L32": {"periods": [7, 8], "days": ["Monday"]},
    "L33": {"periods": [9, 10], "days": ["Monday"]},
    "L34": {"periods": [9, 10], "days": ["Monday"]},
    "L35": {"periods": [7, 8], "days": ["Tuesday"]},
    "L36": {"periods": [7, 8], "days": ["Tuesday"]},
    "L37": {"periods": [9, 10], "days": ["Tuesday"]},
    "L38": {"periods": [9, 10], "days": ["Tuesday"]},
    "L39": {"periods": [7, 8], "days": ["Wednesday"]},
    "L40": {"periods": [7, 8], "days": ["Wednesday"]},
    "L41": {"periods": [9, 10], "days": ["Wednesday"]},
    "L42": {"periods": [9, 10], "days": ["Wednesday"]},
    "L43": {"periods": [7, 8], "days": ["Thursday"]},
    "L44": {"periods": [7, 8], "days": ["Thursday"]},
    "L45": {"periods": [9, 10], "days": ["Thursday"]},
    "L46": {"periods": [9, 10], "days": ["Thursday"]},
    "L47": {"periods": [7, 8], "days": ["Friday"]},
    "L48": {"periods": [7, 8], "days": ["Friday"]},
    "L49": {"periods": [9, 10], "days": ["Friday"]},
    "L50": {"periods": [9, 10], "days": ["Friday"]},
}


def _resolve_slots_to_schedule(slots) -> dict:
    """Convert VIT slot codes to day-grouped schedule with times.
    
    Each theory slot (e.g. A2) maps to MULTIPLE days per week (e.g. Mon/Wed/Fri).
    Each lab slot (e.g. L3) maps to a single day with a 2-period block.
    Tutorial slots (TA2, TB2) are single-period on their parent's days.
    
    Combined entries like "A2+TA2" are split on '+' — each part is resolved
    independently. Duplicate entries for the same course on the same day/time
    are deduplicated.
    """
    from collections import defaultdict
    schedule: dict = defaultdict(list)
    seen: set = set()  # Deduplicate by (day, start_time, course_code)

    for slot_record in slots:
        slot_str = slot_record.slot or ""
        if not slot_str or slot_str.upper() == "NIL":
            continue

        # Split combined slots like "A2+TA2" or "L3+L4"
        individual_slots = [s.strip() for s in slot_str.split("+")]

        for individual in individual_slots:
            timing = VIT_SLOT_TIMING.get(individual)
            if not timing:
                continue

            periods = timing["periods"]
            days = timing["days"]

            # For each day this slot occurs on
            for day in days:
                # Compute time range from periods
                first_period = periods[0]
                last_period = periods[-1]
                start_time = VIT_PERIOD_TIMES[first_period][0]
                end_time = VIT_PERIOD_TIMES[last_period][1]

                # Deduplicate: same course, same day, same start time
                dedup_key = (day, start_time, slot_record.course_code)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                schedule[day].append({
                    "id": slot_record.id,
                    "course_code": slot_record.course_code,
                    "course_name": slot_record.course_name or slot_record.course_code,
                    "start_time": start_time,
                    "end_time": end_time,
                    "slot_type": (slot_record.course_type or "TH").lower(),
                    "venue": slot_record.venue or "",
                })

    # Sort each day's classes by start_time
    for day in schedule:
        schedule[day].sort(key=lambda x: x["start_time"])

    return dict(schedule)


@router.get("/timetable")
async def get_timetable_mapped(session: AsyncSession = Depends(get_session)):
    """Return timetable grouped by day with resolved times (from VIT slot codes)."""
    result = await session.exec(select(TimetableSlot))
    slots = result.all()
    if not slots:
        return {}
    return _resolve_slots_to_schedule(slots)


@router.get("/timetable/free-slots")
async def get_free_slots(day: str = "Monday", session: AsyncSession = Depends(get_session)):
    """Return free time slots for a given day between 8am-8pm."""
    from datetime import datetime as _dt

    # Resolve "today" to actual day name
    if day.lower() == "today":
        day = _dt.now().strftime("%A")

    result = await session.exec(select(TimetableSlot))
    slots = result.all()
    schedule = _resolve_slots_to_schedule(slots)

    day_classes = schedule.get(day, [])

    # Calculate free slots between 8:00 and 20:00
    free_slots = []
    day_start = "08:00"
    day_end = "20:00"

    occupied = [(cls["start_time"], cls["end_time"]) for cls in day_classes]
    occupied.sort()

    # Remove duplicates (overlapping lab slots)
    merged = []
    for start, end in occupied:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    current = day_start
    for start, end in merged:
        if current < start:
            free_slots.append({
                "start_time": current,
                "end_time": start,
                "duration_minutes": _time_diff_minutes(current, start),
            })
        current = max(current, end)

    if current < day_end:
        free_slots.append({
            "start_time": current,
            "end_time": day_end,
            "duration_minutes": _time_diff_minutes(current, day_end),
        })

    total_free = sum(s["duration_minutes"] for s in free_slots)
    return {"day": day, "free_slots": free_slots, "total_free_minutes": total_free}


def _time_diff_minutes(t1: str, t2: str) -> int:
    """Calculate minutes between two HH:MM strings."""
    h1, m1 = map(int, t1.split(":"))
    h2, m2 = map(int, t2.split(":"))
    return (h2 * 60 + m2) - (h1 * 60 + m1)

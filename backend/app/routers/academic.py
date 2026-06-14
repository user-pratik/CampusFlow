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

    risks = [
        calculate_risk(
            course_code=rec.course_code,
            course_title=rec.course_title,
            attended=rec.attended,
            total=rec.total,
        )
        for rec in records
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

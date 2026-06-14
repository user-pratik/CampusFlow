"""Academic data router — serves attendance, marks, profile, and VTOP sync controls."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import AcademicProfile, Attendance, CourseMark

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

"""Academic data router — serves attendance, marks, profile, and VTOP sync controls."""

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import AcademicProfile, Attendance, CourseMark

router = APIRouter()

WORKER_SCRIPT = Path(__file__).resolve().parent.parent.parent / "vtop_sync_worker.py"


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
    """Trigger VTOP scrape. Optionally pass semester_id to use a specific semester.

    Runs in a subprocess because Playwright needs its own event loop on Windows.
    """
    args = [sys.executable, str(WORKER_SCRIPT)]
    if body and body.semester_id:
        args.append(body.semester_id)

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(WORKER_SCRIPT.parent),
        )
        if result.returncode == 0:
            try:
                # Last line of stdout is JSON summary
                lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
                summary = json.loads(lines[-1]) if lines else {}
                return {"status": "completed", "summary": summary}
            except (json.JSONDecodeError, IndexError):
                return {"status": "completed", "output": result.stdout[-500:]}
        else:
            return {"status": "failed", "error": result.stderr[-500:]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "VTOP sync took too long"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/academic/semesters")
async def get_available_semesters():
    """Get available VTOP semesters (runs Playwright to fetch from portal)."""
    script = Path(__file__).resolve().parent.parent.parent / "vtop_get_semesters.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(script.parent),
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            semesters = json.loads(lines[-1]) if lines else {}
            return {"semesters": semesters}
        else:
            return {"semesters": {}, "error": result.stderr[-200:]}
    except Exception as e:
        return {"semesters": {}, "error": str(e)}

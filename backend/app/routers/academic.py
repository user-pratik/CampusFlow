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

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
WORKER_SCRIPT = BACKEND_ROOT / "vtop_sync_worker.py"
LOGIN_SCRIPT = BACKEND_ROOT / "vtop_login_browser.py"


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
    """Trigger VTOP scrape. If session is expired, auto-launches browser login.

    Also triggers WhatsApp QR generation if WhatsApp isn't connected.
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
                lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
                summary = json.loads(lines[-1]) if lines else {}
                # If session expired, report it — don't auto-launch login browser
                if summary.get("success") is False and "session expired" in summary.get("error", "").lower():
                    return {
                        "status": "session_expired",
                        "error": "Session expired — click Sync to open login browser, or run vtop_login_browser.py manually.",
                    }
                return {"status": "completed", "summary": summary}
            except (json.JSONDecodeError, IndexError):
                return {"status": "completed", "output": result.stdout[-500:]}
        else:
            return {"status": "failed", "error": result.stderr[-500:]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "VTOP sync took too long"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/academic/login")
async def launch_vtop_login():
    """Manually trigger VTOP browser login (opens Chromium for reCAPTCHA solving)."""
    _launch_vtop_login()
    return {"status": "launched", "message": "Browser opened — solve reCAPTCHA and click Login."}


@router.post("/academic/full-sync")
async def full_sync():
    """Full sync: launches VTOP login browser + WhatsApp QR + waits for login then syncs.

    This is the "one button does everything" endpoint:
    1. Opens VTOP login browser (user solves reCAPTCHA)
    2. Triggers WhatsApp QR code generation (if not connected)
    3. After VTOP login succeeds, automatically runs the data sync
    """
    results = {
        "vtop_login": "skipped",
        "whatsapp": "skipped",
        "vtop_sync": "pending",
    }

    # Step 1: Check if VTOP session is valid
    session_file = BACKEND_ROOT / "vtop_session.json"
    session_valid = False
    if session_file.exists():
        # Quick check: try running the worker
        try:
            check = subprocess.run(
                [sys.executable, str(WORKER_SCRIPT)],
                capture_output=True,
                text=True,
                timeout=90,
                cwd=str(BACKEND_ROOT),
            )
            if check.returncode == 0:
                lines = [l for l in check.stdout.strip().split("\n") if l.strip()]
                summary = json.loads(lines[-1]) if lines else {}
                if summary.get("success"):
                    session_valid = True
                    results["vtop_login"] = "session_valid"
                    results["vtop_sync"] = "completed"
                    results["sync_summary"] = summary
        except Exception:
            pass

    if not session_valid:
        # Launch browser login
        _launch_vtop_login()
        results["vtop_login"] = "browser_launched"
        results["vtop_sync"] = "waiting_for_login"

    # Step 2: WhatsApp — trigger QR if not connected
    try:
        from app.startup import get_ngrok_url, EVOLUTION_BASE, EVOLUTION_API_KEY, INSTANCE_NAME
        import httpx

        ngrok_url = get_ngrok_url()
        if ngrok_url:
            headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
            # Check connection state
            import asyncio
            import httpx as httpx_lib
            async with httpx_lib.AsyncClient(timeout=5) as client:
                r = await client.get(
                    f"{EVOLUTION_BASE}/instance/connectionState/{INSTANCE_NAME}",
                    headers=headers,
                )
                if r.status_code == 200:
                    data = r.json()
                    state = data.get("instance", data).get("state", "unknown")
                    if state == "open":
                        results["whatsapp"] = "already_connected"
                    else:
                        # Regenerate QR
                        from app.startup import _fetch_and_save_qr
                        await _fetch_and_save_qr(headers)
                        results["whatsapp"] = "qr_generated"
                else:
                    results["whatsapp"] = "evolution_api_error"
        else:
            results["whatsapp"] = "ngrok_not_active"
    except Exception as e:
        results["whatsapp"] = f"error: {str(e)[:100]}"

    return results


def _launch_vtop_login():
    """Launch the VTOP login browser script as a detached background process."""
    try:
        # Launch as a detached process so it doesn't block the server
        subprocess.Popen(
            [sys.executable, str(LOGIN_SCRIPT)],
            cwd=str(BACKEND_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # On Windows, CREATE_NEW_PROCESS_GROUP detaches the process
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    except Exception:
        # Fallback without creation flags
        subprocess.Popen(
            [sys.executable, str(LOGIN_SCRIPT)],
            cwd=str(BACKEND_ROOT),
        )


@router.get("/academic/semesters")
async def get_available_semesters():
    """Get available VTOP semesters (runs Playwright to fetch from portal)."""
    script = BACKEND_ROOT / "vtop_get_semesters.py"
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

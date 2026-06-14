"""VTOP API Router — handles login launch, session management, and data syncing.

Endpoints:
- POST /api/vtop/launch-login  — Launch Playwright browser for VTOP login
- POST /api/vtop/store-session — Import cookies from vtop_session.json into DB
- GET  /api/vtop/session-status — Check if stored session is valid
- GET  /api/vtop/semesters      — Fetch available semesters
- POST /api/vtop/sync           — Trigger data sync for a semester
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.connectors.vtop.session_store import SessionStore
from app.connectors.vtop.session_validator import SessionValidator, SessionStatus
from app.connectors.vtop.sync_orchestrator import SyncOrchestrator, SyncResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vtop", tags=["vtop"])


# ─── Request / Response models ───────────────────────────────────────────────


class SyncRequest(BaseModel):
    """Request body for the /sync endpoint."""
    semester_id: str


class SemesterList(BaseModel):
    """Response model for the /semesters endpoint."""
    semesters: dict[str, str]
    error: str | None = None


# ─── Login (Playwright-based) ────────────────────────────────────────────────

_login_process = None


@router.post("/launch-login")
async def launch_login():
    """Launch the Playwright browser for VTOP login.

    Only one browser process runs at a time. If already running, returns
    'already_running' status.

    The frontend polls /api/vtop/session-status until it returns 'valid'.
    """
    global _login_process
    import subprocess
    import sys
    from pathlib import Path

    # Prevent multiple simultaneous launches
    if _login_process is not None and _login_process.poll() is None:
        return {"status": "already_running", "message": "Login browser is already open."}

    login_script = Path(__file__).resolve().parent.parent.parent / "vtop_login_browser.py"

    if not login_script.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "Login script not found", "path": str(login_script)},
        )

    try:
        # Launch with visible console so errors are readable
        _login_process = subprocess.Popen(
            [sys.executable, str(login_script)],
            cwd=str(login_script.parent),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        logger.info("Launched VTOP login browser script (PID: %d).", _login_process.pid)
        return {"status": "launched", "message": "Browser opened — solve reCAPTCHA and click Login."}
    except Exception as e:
        logger.error("Failed to launch login browser: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to launch browser: {str(e)}"},
        )


@router.post("/store-session")
async def store_session_from_file():
    """Read cookies from vtop_session.json and store them in the DB SessionStore.

    Can be called explicitly, but the session-status endpoint also auto-imports.
    """
    import json
    from pathlib import Path

    session_file = Path(__file__).resolve().parent.parent.parent / "vtop_session.json"

    if not session_file.exists():
        return {"status": "no_file", "message": "No session file found."}

    try:
        with open(session_file, "r", encoding="utf-8") as f:
            session_data = json.load(f)

        cookies = session_data.get("cookies", [])
        if not cookies:
            return {"status": "empty", "message": "Session file has no cookies."}

        # Convert Playwright cookie format to our format
        cookie_list = [
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", "vtopcc.vit.ac.in"),
                "path": c.get("path", "/"),
            }
            for c in cookies
        ]

        # Check for JSESSIONID
        has_jsessionid = any(c["name"] == "JSESSIONID" for c in cookie_list)
        if not has_jsessionid:
            return {"status": "invalid", "message": "No JSESSIONID cookie found."}

        # Store in SessionStore DB
        session_store = SessionStore()
        await session_store.save_session(cookies=cookie_list, csrf_token=None)

        return {"status": "stored", "message": f"Stored {len(cookie_list)} cookies in DB."}
    except Exception as e:
        logger.error("Failed to store session from file: %s", e)
        return {"status": "error", "message": str(e)}


# ─── Session & Sync ──────────────────────────────────────────────────────────


@router.get("/session-status", response_model=SessionStatus)
async def session_status() -> SessionStatus:
    """Check whether stored VTOP session cookies are still valid.

    Also auto-imports cookies from vtop_session.json if no DB session exists.

    Returns a SessionStatus with one of:
    - 'valid': session cookies are still authenticated
    - 'session_expired': cookies exist but VTOP redirected to login
    - 'no_session': no stored session found
    - 'validation_failed': network error or timeout reaching VTOP
    """
    validator = SessionValidator()
    return await validator.validate()


@router.get("/semesters", response_model=SemesterList)
async def get_semesters() -> SemesterList:
    """Fetch available semesters from VTOP using stored session cookies."""
    session_store = SessionStore()
    orchestrator = SyncOrchestrator(session_store)
    try:
        semesters = await orchestrator.get_semesters()
        return SemesterList(semesters=semesters)
    except Exception as e:
        logger.exception("Failed to fetch semesters: %s", e)
        return SemesterList(semesters={}, error=str(e))
    finally:
        await orchestrator.close()


@router.post("/sync", response_model=SyncResult)
async def trigger_sync(body: SyncRequest) -> SyncResult:
    """Trigger a full data sync for the given semester.

    Scrapes attendance, marks, and CGPA from VTOP using httpx with
    stored session cookies and persists to the database.
    """
    session_store = SessionStore()
    orchestrator = SyncOrchestrator(session_store)
    try:
        result = await orchestrator.sync_all(body.semester_id)
        return result
    finally:
        await orchestrator.close()

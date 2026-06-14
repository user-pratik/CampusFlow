"""VTOP session validator.

Verifies whether stored session cookies are still valid by making
a GET request to an authenticated VTOP page and checking for login redirects.
"""

import logging

import httpx
from pydantic import BaseModel
from typing import Literal

from app.connectors.vtop.session_store import SessionStore

logger = logging.getLogger(__name__)

VTOP_CONTENT_URL = "https://vtopcc.vit.ac.in/vtop/content"
VALIDATION_TIMEOUT = 10.0  # seconds


class SessionStatus(BaseModel):
    status: Literal["valid", "session_expired", "no_session", "validation_failed"]
    error: str | None = None
    established_at: str | None = None  # ISO timestamp


class SessionValidator:
    """Checks if stored VTOP session cookies are still valid."""

    def __init__(self, session_store: SessionStore | None = None):
        self.session_store = session_store or SessionStore()

    async def validate(self) -> SessionStatus:
        """GET /vtop/content with stored cookies, check for login redirect.

        First checks the DB for stored cookies. If none found, tries to
        load from vtop_session.json (written by vtop_login_browser.py) and
        stores them in the DB.

        Returns SessionStatus with:
        - 'valid' if response stays on authenticated page
        - 'session_expired' if response redirects to login page
        - 'no_session' if no stored session exists
        - 'validation_failed' on timeout or network error
        """
        # Check if we have a stored session in DB
        record = await self.session_store.get_active_session()

        # If no DB session, try loading from vtop_session.json
        if record is None:
            await self._try_import_from_file()
            record = await self.session_store.get_active_session()

        if record is None:
            return SessionStatus(status="no_session")

        # Load cookies from the active session
        cookies = await self.session_store.get_cookies_as_httpx()
        if cookies is None:
            return SessionStatus(status="no_session")

        try:
            async with httpx.AsyncClient(
                timeout=VALIDATION_TIMEOUT,
                follow_redirects=True,
                verify=False,
                cookies=cookies,
            ) as client:
                response = await client.get(VTOP_CONTENT_URL)

            # Check if final URL redirected to login page
            final_url = str(response.url)
            if "/vtop/login" in final_url:
                logger.info("VTOP session expired (redirected to login).")
                await self.session_store.mark_expired()

                # Try re-importing from file — vtop_login_browser.py may have
                # written a newer session since we last checked
                await self._try_import_from_file()
                new_record = await self.session_store.get_active_session()
                if new_record and new_record.id != record.id:
                    # A new session was imported — validate it
                    logger.info("Found newer session in file, re-validating...")
                    return await self.validate()

                return SessionStatus(
                    status="session_expired",
                    established_at=record.established_at.isoformat(),
                )

            # Session is still valid
            logger.info("VTOP session validated successfully.")
            return SessionStatus(
                status="valid",
                established_at=record.established_at.isoformat(),
            )

        except httpx.TimeoutException:
            logger.warning("VTOP session validation timed out (>%ss).", VALIDATION_TIMEOUT)
            return SessionStatus(
                status="validation_failed",
                error="VTOP is unreachable: request timed out",
            )
        except httpx.HTTPError as exc:
            logger.warning("VTOP session validation failed: %s", exc)
            return SessionStatus(
                status="validation_failed",
                error=f"VTOP is unreachable: {type(exc).__name__}",
            )

    async def _try_import_from_file(self) -> None:
        """Try to import session cookies from vtop_session.json into the DB.

        Only imports if the file exists and contains a JSESSIONID cookie.
        Checks file mtime to avoid re-importing the same stale file.
        """
        import json
        import os
        from pathlib import Path

        session_file = Path(__file__).resolve().parent.parent.parent.parent / "vtop_session.json"
        if not session_file.exists():
            return

        try:
            # Check if file was modified recently (within last 10 minutes)
            # This avoids re-importing a stale file repeatedly
            file_mtime = os.path.getmtime(session_file)
            import time
            if time.time() - file_mtime > 600:  # older than 10 minutes
                return

            with open(session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            cookies = session_data.get("cookies", [])
            if not cookies:
                return

            cookie_list = [
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", "vtopcc.vit.ac.in"),
                    "path": c.get("path", "/"),
                }
                for c in cookies
            ]

            if not any(c["name"] == "JSESSIONID" for c in cookie_list):
                return

            await self.session_store.save_session(cookies=cookie_list, csrf_token=None)
            logger.info("Imported %d cookies from vtop_session.json into DB.", len(cookie_list))
        except Exception as e:
            logger.warning("Failed to import session from file: %s", e)

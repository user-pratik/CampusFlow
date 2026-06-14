"""Sync Orchestrator — HTTP-based VTOP scraping using stored session cookies.

Replaces the Playwright-based VTOPConnector with plain httpx requests.
Uses cookies from SessionStore and existing parsers from scrapers.py.
"""

import logging
from datetime import datetime
from typing import Literal

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel
from sqlmodel import delete

from app.connectors.vtop.scrapers import (
    parse_academic_history,
    parse_attendance,
    parse_marks,
)
from app.connectors.vtop.session_store import SessionStore
from app.database import async_session_maker
from app.models import AcademicProfile, Attendance, CourseMark

logger = logging.getLogger(__name__)

VTOP_BASE_URL = "https://vtopcc.vit.ac.in/vtop"


class SyncResult(BaseModel):
    """Result of a sync operation."""

    status: Literal["completed", "session_expired", "failed"]
    attendance_count: int = 0
    marks_count: int = 0
    profile_updated: bool = False
    error: str | None = None


class SyncOrchestrator:
    """Orchestrates VTOP data scraping via HTTP POST with stored cookies.

    Uses the SessionStore to load cookies, extracts CSRF tokens from
    VTOP pages, and persists scraped data to the database.
    """

    def __init__(self, session_store: SessionStore):
        self.session_store = session_store
        self.client: httpx.AsyncClient | None = None
        self._csrf: str = ""
        self._authorized_id: str = ""

    async def _init_client(self) -> bool:
        """Initialize httpx client with stored cookies and extract CSRF token + authorizedID.

        Returns True if client is ready with valid session.
        """
        cookies = await self.session_store.get_cookies_as_httpx()
        if cookies is None:
            logger.error("No active session cookies found.")
            return False

        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=False,
            cookies=cookies,
        )

        # Fetch VTOP content page to extract CSRF token and authorizedID
        try:
            resp = await self.client.get(f"{VTOP_BASE_URL}/content")
            if self._is_login_redirect(resp):
                logger.warning("Session expired — redirected to login page.")
                await self.session_store.mark_expired()
                return False

            soup = BeautifulSoup(resp.text, "lxml")
            self._csrf = self._extract_csrf(soup)
            if not self._csrf:
                logger.warning("Could not extract CSRF token from content page.")

            # Extract authorizedID (required for all VTOP AJAX calls)
            auth_tag = soup.find("input", {"id": "authorizedIDX"})
            if auth_tag and auth_tag.get("value"):
                self._authorized_id = auth_tag["value"]
            else:
                # Try alternate: hidden input named authorizedID
                auth_tag = soup.find("input", {"name": "authorizedID"})
                if auth_tag and auth_tag.get("value"):
                    self._authorized_id = auth_tag["value"]

            if not self._authorized_id:
                logger.warning("Could not extract authorizedID from content page.")

            logger.info("VTOP client initialized. CSRF: %s..., AuthID: %s...",
                       self._csrf[:10] if self._csrf else "NONE",
                       self._authorized_id[:10] if self._authorized_id else "NONE")
            return True

        except httpx.TimeoutException:
            logger.error("Timeout fetching VTOP content page for CSRF extraction.")
            return False
        except Exception as e:
            logger.error("Failed to initialize VTOP client: %s", e)
            return False

    async def get_semesters(self) -> dict[str, str]:
        """Fetch semester list from VTOP via HTTP POST.

        Uses the same endpoint as the Android app: academics/common/StudentTimeTableChn

        Returns:
            Dict mapping semester display name to semester ID.
            Empty dict on failure.
        """
        if not self.client and not await self._init_client():
            return {}

        try:
            import time
            resp = await self.client.post(
                f"{VTOP_BASE_URL}/academics/common/StudentTimeTableChn",
                data={
                    "verifyMenu": "true",
                    "authorizedID": self._authorized_id,
                    "_csrf": self._csrf,
                    "nocache": f"@{int(time.time() * 1000)}",
                },
            )

            if self._is_login_redirect(resp):
                logger.warning("Session expired while fetching semesters.")
                await self.session_store.mark_expired()
                return {}

            # Update CSRF if present in response
            soup = BeautifulSoup(resp.text, "lxml")
            self._update_csrf(soup)

            # Parse semester options from the HTML select element
            semesters: dict[str, str] = {}
            select_tag = soup.find("select", {"id": True})
            if select_tag:
                for option in select_tag.find_all("option"):
                    value = option.get("value", "").strip()
                    text = option.get_text(strip=True)
                    if value and text and value != "0":
                        semesters[text] = value

            logger.info("Fetched %d semesters from VTOP.", len(semesters))
            return semesters

        except httpx.TimeoutException:
            logger.error("Timeout fetching semesters from VTOP.")
            return {}
        except Exception as e:
            logger.error("Failed to fetch semesters: %s", e)
            return {}

    async def sync_all(self, semester_id: str) -> SyncResult:
        """Scrape attendance, marks, CGPA and persist to database.

        Aborts on login redirect at any step (session expired).

        Args:
            semester_id: The VTOP semester identifier to scrape.

        Returns:
            SyncResult with status and counts.
        """
        if not self.client and not await self._init_client():
            return SyncResult(
                status="session_expired",
                error="No valid session — please log in again.",
            )

        try:
            # Scrape attendance
            attendance_records = await self._scrape_attendance(semester_id)
            if attendance_records is None:
                return SyncResult(
                    status="session_expired",
                    error="Session expired while scraping attendance.",
                )

            # Scrape marks
            marks_records = await self._scrape_marks(semester_id)
            if marks_records is None:
                return SyncResult(
                    status="session_expired",
                    error="Session expired while scraping marks.",
                )

            # Scrape CGPA
            profile_data = await self._scrape_cgpa()
            if profile_data is None:
                return SyncResult(
                    status="session_expired",
                    error="Session expired while scraping CGPA.",
                )

            # Persist data (only if non-empty per Req 6.6)
            await self._persist_attendance(attendance_records)
            await self._persist_marks(marks_records)
            await self._persist_profile(profile_data)

            return SyncResult(
                status="completed",
                attendance_count=len(attendance_records),
                marks_count=len(marks_records),
                profile_updated=profile_data.get("cgpa", 0) > 0,
            )

        except httpx.TimeoutException as e:
            logger.error("Timeout during sync: %s", e)
            return SyncResult(status="failed", error="Request timed out.")
        except Exception as e:
            logger.exception("Sync failed: %s", e)
            return SyncResult(status="failed", error=str(e))

    async def _scrape_attendance(self, semester_id: str) -> list[dict] | None:
        """Scrape attendance data for a semester.

        Returns:
            List of attendance records, or None if session expired.
        """
        resp = await self.client.post(
            f"{VTOP_BASE_URL}/processViewStudentAttendance",
            data={
                "_csrf": self._csrf,
                "semesterSubId": semester_id,
                "authorizedID": self._authorized_id,
            },
        )

        if self._is_login_redirect(resp):
            logger.warning("Session expired during attendance scrape.")
            await self.session_store.mark_expired()
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        self._update_csrf(soup)
        records = parse_attendance(soup)
        logger.info("Scraped %d attendance records.", len(records))
        return records

    async def _scrape_marks(self, semester_id: str) -> list[dict] | None:
        """Scrape marks data for a semester.

        Returns:
            List of marks records, or None if session expired.
        """
        resp = await self.client.post(
            f"{VTOP_BASE_URL}/examinations/doStudentMarkView",
            data={
                "semesterSubId": semester_id,
                "authorizedID": self._authorized_id,
                "_csrf": self._csrf,
            },
        )

        if self._is_login_redirect(resp):
            logger.warning("Session expired during marks scrape.")
            await self.session_store.mark_expired()
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        self._update_csrf(soup)
        records = parse_marks(soup)
        logger.info("Scraped %d marks records.", len(records))
        return records

    async def _scrape_cgpa(self) -> dict | None:
        """Scrape CGPA / academic history.

        Returns:
            Dict with cgpa, total_credits, or None if session expired.
        """
        import time
        resp = await self.client.post(
            f"{VTOP_BASE_URL}/examinations/examGradeView/StudentGradeHistory",
            data={
                "verifyMenu": "true",
                "authorizedID": self._authorized_id,
                "_csrf": self._csrf,
                "nocache": f"@{int(time.time() * 1000)}",
            },
        )

        if self._is_login_redirect(resp):
            logger.warning("Session expired during CGPA scrape.")
            await self.session_store.mark_expired()
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        self._update_csrf(soup)
        data = parse_academic_history(soup)
        logger.info("Scraped academic profile: CGPA=%.2f", data.get("cgpa", 0))
        return data

    async def _persist_attendance(self, records: list[dict]) -> None:
        """Persist attendance records to DB, replacing existing ones.

        Skips if records list is empty (Req 6.6 — preserve existing data).
        """
        if not records:
            logger.info("No attendance records to persist — preserving existing data.")
            return

        async with async_session_maker() as session:
            await session.exec(delete(Attendance))
            for rec in records:
                title = rec.get("course_title", "")
                title = title.split("\n")[0].strip() if "\n" in title else title.strip()
                if not title:
                    title = rec.get("course_code", "Unknown")

                session.add(Attendance(
                    course_code=rec["course_code"],
                    course_title=title,
                    percentage=float(rec.get("percentage", 0)),
                    attended=int(rec.get("attended", 0)),
                    total=int(rec.get("total", 0)),
                    updated_at=datetime.utcnow(),
                ))
            await session.commit()
        logger.info("Persisted %d attendance records.", len(records))

    async def _persist_marks(self, records: list[dict]) -> None:
        """Persist marks records to DB, replacing existing ones.

        Skips if records list is empty (Req 6.6 — preserve existing data).
        """
        if not records:
            logger.info("No marks records to persist — preserving existing data.")
            return

        async with async_session_maker() as session:
            await session.exec(delete(CourseMark))
            for rec in records:
                session.add(CourseMark(
                    course_code=rec.get("course_code", ""),
                    course_title=rec.get("course_title", ""),
                    mark_title=rec.get("mark_title", ""),
                    max_mark=rec.get("max_mark"),
                    weightage_pct=rec.get("weightage_pct"),
                    score=rec.get("score"),
                    weightage_mark=rec.get("weightage_mark"),
                    status=rec.get("status"),
                    updated_at=datetime.utcnow(),
                ))
            await session.commit()
        logger.info("Persisted %d marks records.", len(records))

    async def _persist_profile(self, data: dict) -> None:
        """Persist academic profile to DB, replacing existing.

        Skips if both CGPA and credits are zero (nothing meaningful to store).
        """
        if data.get("cgpa", 0) == 0 and data.get("total_credits", 0) == 0:
            logger.info("No meaningful profile data — preserving existing.")
            return

        async with async_session_maker() as session:
            await session.exec(delete(AcademicProfile))
            session.add(AcademicProfile(
                cgpa=data["cgpa"],
                total_credits=data["total_credits"],
                overall_attendance=data.get("overall_attendance"),
                semester_name=data.get("semester_name"),
                updated_at=datetime.utcnow(),
            ))
            await session.commit()
        logger.info(
            "Persisted academic profile: CGPA=%.2f, Credits=%d",
            data["cgpa"],
            data["total_credits"],
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _is_login_redirect(self, response: httpx.Response) -> bool:
        """Check if response indicates session expired (redirected to login)."""
        return "/vtop/login" in str(response.url)

    def _extract_csrf(self, soup: BeautifulSoup) -> str:
        """Extract CSRF token from a parsed HTML page."""
        # Check hidden input first
        tag = soup.find("input", {"name": "_csrf"})
        if tag and tag.get("value"):
            return tag["value"]
        # Fallback to meta tag
        meta = soup.find("meta", {"name": "_csrf"})
        if meta and meta.get("content"):
            return meta["content"]
        return ""

    def _update_csrf(self, soup: BeautifulSoup) -> None:
        """Update CSRF token if a new one is found in the response."""
        new_csrf = self._extract_csrf(soup)
        if new_csrf:
            self._csrf = new_csrf

"""VTOP Connector — orchestrates browser-based scraping and data persistence."""

import logging
from datetime import datetime

from sqlmodel import delete

from app.connectors.vtop.browser_scraper import VTOPBrowserScraper
from app.database import async_session_maker
from app.models import AcademicProfile, Attendance, CourseMark

logger = logging.getLogger(__name__)


class VTOPConnector:
    """Full connector: browser login → scrape → persist academic data."""

    def __init__(self):
        self.scraper = VTOPBrowserScraper()
        self._semester_id: str | None = None
        self._semester_name: str | None = None

    async def run(self) -> dict:
        """Execute full scraping pipeline using Playwright.

        Returns:
            Summary dict with counts of records scraped/inserted.
        """
        summary = {
            "attendance": 0,
            "marks": 0,
            "academic_profile": False,
            "announcements": 0,
            "success": False,
        }

        try:
            # Step 1: Start browser with saved session
            if not await self.scraper.start():
                logger.error("VTOP browser session failed — aborting scrape.")
                return summary

            # Step 2: Get available semesters and pick the target
            if self._semester_id:
                sem_id = self._semester_id
                sem_name = self._semester_name or sem_id
            else:
                semesters = await self.scraper.get_semesters()
                if not semesters:
                    logger.warning("No semesters found.")
                    await self.scraper.close()
                    return summary
                sem_name = list(semesters.keys())[0]
                sem_id = semesters[sem_name]

            logger.info("Using semester: %s (%s)", sem_name, sem_id)

            # Step 3: Scrape attendance
            attendance_data = await self.scraper.scrape_attendance(sem_id)
            summary["attendance"] = len(attendance_data)

            # Step 4: Scrape marks
            marks_data = await self.scraper.scrape_marks(sem_id)
            summary["marks"] = len(marks_data)

            # Step 5: Scrape CGPA
            profile_data = await self.scraper.scrape_cgpa()
            summary["academic_profile"] = profile_data.get("cgpa", 0) > 0

            # Compute overall attendance
            total_attended = sum(r.get("attended", 0) for r in attendance_data)
            total_classes = sum(r.get("total", 0) for r in attendance_data)
            overall_att = (total_attended / total_classes * 100) if total_classes > 0 else 0
            profile_data["overall_attendance"] = round(overall_att, 1)
            profile_data["semester_name"] = sem_name

            # Step 6: Persist to DB
            await self._persist_attendance(attendance_data)
            await self._persist_marks(marks_data)
            await self._persist_profile(profile_data)

            summary["success"] = True
            logger.info("VTOP scrape complete: %s", summary)

        except Exception as e:
            logger.exception("VTOP connector failed: %s", e)
        finally:
            await self.scraper.close()

        return summary

    async def _persist_attendance(self, records: list[dict]) -> None:
        """Write attendance records to DB (replace existing)."""
        if not records:
            return

        async with async_session_maker() as session:
            await session.exec(delete(Attendance))
            for rec in records:
                # Clean course_title (may have faculty name/whitespace noise)
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
        """Store each individual mark entry directly (no aggregation).

        Each record maps to one row in course_marks with the exact
        VTOP fields: mark_title, max_mark, weightage_pct, score, weightage_mark, status.
        """
        if not records:
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
        logger.info("Persisted %d individual mark entries.", len(records))

    async def _persist_profile(self, data: dict) -> None:
        """Write academic profile to DB (single row, replace)."""
        if data.get("cgpa", 0) == 0 and data.get("total_credits", 0) == 0:
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
        logger.info("Persisted academic profile: CGPA=%.2f, Credits=%d", data["cgpa"], data["total_credits"])

    async def _route_announcements(self, messages: list[dict]) -> None:
        """Route announcements through the existing LLM pipeline (NoticeAgent → SchedulerAgent)."""
        from app.connectors.vtop.pipeline import route_to_llm_pipeline
        await route_to_llm_pipeline(messages)

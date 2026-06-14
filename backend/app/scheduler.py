"""APScheduler configuration for CampusFlow.

Provides an AsyncIOScheduler instance with clean start/stop lifecycle integration.
Jobs are registered via `register_jobs(scheduler)` — agents add their scheduled
work there.

Existing jobs:
- Daily digest at 8:00 AM
- VTOP polling at configurable interval
"""

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ─── Job Implementations ──────────────────────────────────────────────────────


async def _generate_daily_digest():
    """Scheduled job: run DigestAgent to create the morning briefing."""
    from app.agents.digest_agent import DigestAgent

    agent = DigestAgent()
    try:
        result = await agent.execute({})
        logger.info(
            "Daily digest generated (id=%s): %s...",
            result["digest_id"],
            result["content"][:60],
        )
    except Exception as e:
        logger.exception("Daily digest generation failed: %s", e)


async def _poll_vtop():
    """Scheduled job: scrape VTOP portal for fresh academic data.

    Skips if no session file exists (avoids launching browsers pointlessly).
    """
    from pathlib import Path

    session_file = Path(__file__).resolve().parent.parent / "vtop_session.json"
    if not session_file.exists():
        logger.debug("VTOP poll skipped — no session file.")
        return

    from app.connectors.vtop.connector import VTOPConnector

    connector = VTOPConnector()
    try:
        summary = await connector.run()
        logger.info("VTOP poll complete: %s", summary)
    except Exception as e:
        logger.exception("VTOP poll failed: %s", e)


async def _check_deadline_alerts():
    """Scheduled job (hourly): create notifications for deadlines due within 24hrs.

    Queries Deadline rows where status='upcoming' and due_datetime is within the
    next 24 hours. Creates a Notification for each, deduplicating by checking
    if a notification already exists with link='deadline:{id}'.
    """
    from datetime import datetime, timedelta

    from sqlmodel import select

    from app.database import async_session_maker
    from app.models import Deadline, Notification

    now = datetime.utcnow()
    window_end = now + timedelta(hours=24)

    try:
        async with async_session_maker() as session:
            # Find upcoming deadlines due within 24hrs
            result = await session.exec(
                select(Deadline)
                .where(Deadline.status == "upcoming")
                .where(Deadline.due_datetime >= now)
                .where(Deadline.due_datetime <= window_end)
            )
            deadlines = result.all()

            if not deadlines:
                logger.debug("No deadlines due within 24hrs.")
                return

            # Check existing notifications to avoid duplicates
            deadline_links = [f"deadline:{d.id}" for d in deadlines]
            existing_result = await session.exec(
                select(Notification.link).where(Notification.link.in_(deadline_links))
            )
            existing_links = set(existing_result.all())

            created = 0
            for deadline in deadlines:
                link = f"deadline:{deadline.id}"
                if link in existing_links:
                    continue

                hours_left = max(0, int((deadline.due_datetime - now).total_seconds() / 3600))

                # Determine priority based on urgency
                if hours_left <= 3:
                    priority = "urgent"
                elif hours_left <= 12:
                    priority = "high"
                else:
                    priority = "normal"

                notification = Notification(
                    title=f"⏰ Due in {hours_left}h: {deadline.title}",
                    message=f"{deadline.title} is due {deadline.due_datetime.strftime('%b %d at %H:%M')}. "
                            f"Category: {deadline.category}. Source: {deadline.source}.",
                    source_agent="Deadline Agent",
                    priority=priority,
                    is_read=False,
                    link=link,
                )
                session.add(notification)
                created += 1

            if created:
                await session.commit()
                logger.info("Created %d deadline alert notifications.", created)

    except Exception as e:
        logger.exception("Deadline alert check failed: %s", e)


async def _check_placement_countdown():
    """Scheduled job (daily): notify about placement drives within 3 days.

    For PlacementDrive rows with status='upcoming', drive_date within 3 days,
    and eligibility_status != 'Likely Not Eligible', creates a Notification.
    Deduplicates per drive per day (link='placement:{id}:{date}').
    """
    from datetime import datetime, timedelta

    from sqlmodel import select

    from app.agents.placement_prep_agent import check_eligibility
    from app.database import async_session_maker
    from app.models import Notification, PlacementDrive

    now = datetime.utcnow()
    window_end = now + timedelta(days=3)
    today_str = now.strftime("%Y-%m-%d")

    try:
        async with async_session_maker() as session:
            # Find upcoming drives within 3 days
            result = await session.exec(
                select(PlacementDrive)
                .where(PlacementDrive.status == "upcoming")
                .where(PlacementDrive.drive_date != None)  # noqa: E711
                .where(PlacementDrive.drive_date >= now)
                .where(PlacementDrive.drive_date <= window_end)
            )
            drives = result.all()

            if not drives:
                logger.debug("No placement drives within 3 days.")
                return

            # Filter: skip "Likely Not Eligible"
            eligible_drives = [d for d in drives if check_eligibility(d) != "Likely Not Eligible"]

            if not eligible_drives:
                logger.debug("All nearby drives are ineligible — skipping notifications.")
                return

            # Deduplicate: check existing notifications for today
            links = [f"placement:{d.id}:{today_str}" for d in eligible_drives]
            existing_result = await session.exec(
                select(Notification.link).where(Notification.link.in_(links))
            )
            existing_links = set(existing_result.all())

            created = 0
            for drive in eligible_drives:
                link = f"placement:{drive.id}:{today_str}"
                if link in existing_links:
                    continue

                days_left = max(0, (drive.drive_date - now).days)
                days_label = "today" if days_left == 0 else f"in {days_left} day{'s' if days_left != 1 else ''}"

                notification = Notification(
                    title=f"💼 {drive.company_name} drive {days_label}",
                    message=f"{drive.company_name}{' — ' + drive.role if drive.role else ''} "
                            f"is {days_label}. Check your prep checklist!",
                    source_agent="Placement Agent",
                    priority="high" if days_left <= 1 else "normal",
                    is_read=False,
                    link=f"placement:{drive.id}",
                )
                session.add(notification)
                created += 1

            if created:
                await session.commit()
                logger.info("Created %d placement countdown notifications.", created)

    except Exception as e:
        logger.exception("Placement countdown check failed: %s", e)


# ─── Job Registration ─────────────────────────────────────────────────────────


def register_jobs(sched: AsyncIOScheduler) -> None:
    """Register all scheduled jobs with the scheduler.

    This is the single entry point for adding recurring work.
    New agents should add their jobs here.

    Args:
        sched: The AsyncIOScheduler instance to register jobs on.
    """
    # Daily digest at 8:00 AM
    sched.add_job(
        _generate_daily_digest,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_digest",
        name="Generate morning briefing at 8:00 AM",
        replace_existing=True,
    )

    # VTOP polling at configured interval
    poll_interval = int(os.getenv("VTOP_POLL_INTERVAL", "1800"))
    sched.add_job(
        _poll_vtop,
        trigger=IntervalTrigger(seconds=poll_interval),
        id="vtop_poll",
        name=f"Poll VTOP portal every {poll_interval}s",
        replace_existing=True,
    )

    # Deadline alerts — check hourly for deadlines due within 24hrs
    sched.add_job(
        _check_deadline_alerts,
        trigger=IntervalTrigger(hours=1),
        id="deadline_alerts",
        name="Check for deadlines due within 24hrs (hourly)",
        replace_existing=True,
    )

    # Placement countdown — daily at 7:30 AM for drives within 3 days
    sched.add_job(
        _check_placement_countdown,
        trigger=CronTrigger(hour=7, minute=30),
        id="placement_countdown",
        name="Notify about placement drives within 3 days (daily)",
        replace_existing=True,
    )

    logger.info(
        "Registered %d scheduled jobs.",
        len(sched.get_jobs()),
    )


# ─── Lifecycle ────────────────────────────────────────────────────────────────


def start_scheduler():
    """Configure jobs and start the APScheduler. Call during app lifespan startup."""
    register_jobs(scheduler)
    scheduler.start()
    logger.info("Scheduler started with %d jobs.", len(scheduler.get_jobs()))


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

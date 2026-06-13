"""APScheduler configuration for CampusFlow.

Runs the DigestAgent every morning at 8:00 AM.
Polls VTOP portal every VTOP_POLL_INTERVAL seconds (default: 30 min).
"""

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


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
    """Scheduled job: scrape VTOP portal for fresh academic data."""
    from app.connectors.vtop.connector import VTOPConnector

    connector = VTOPConnector()
    try:
        summary = await connector.run()
        logger.info("VTOP poll complete: %s", summary)
    except Exception as e:
        logger.exception("VTOP poll failed: %s", e)


def start_scheduler():
    """Configure and start the APScheduler. Call during app lifespan startup."""
    # Daily digest at 8:00 AM
    scheduler.add_job(
        _generate_daily_digest,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_digest",
        name="Generate morning briefing at 8:00 AM",
        replace_existing=True,
    )

    # VTOP polling at configured interval
    poll_interval = int(os.getenv("VTOP_POLL_INTERVAL", "1800"))
    scheduler.add_job(
        _poll_vtop,
        trigger=IntervalTrigger(seconds=poll_interval),
        id="vtop_poll",
        name=f"Poll VTOP portal every {poll_interval}s",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started — digest at 08:00, VTOP poll every %ds.", poll_interval)


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

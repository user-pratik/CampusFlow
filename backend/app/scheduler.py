"""APScheduler configuration for CampusFlow.

Runs the DigestAgent every morning at 8:00 AM.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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


def start_scheduler():
    """Configure and start the APScheduler. Call during app lifespan startup."""
    scheduler.add_job(
        _generate_daily_digest,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_digest",
        name="Generate morning briefing at 8:00 AM",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — daily digest at 08:00.")


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

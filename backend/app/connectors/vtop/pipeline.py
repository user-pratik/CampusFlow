"""Pipeline routing — sends VTOP announcements through the existing LLM pipeline."""

import logging

from sqlmodel import select

from app.agents.notice_agent import NoticeAgent
from app.agents.scheduler_agent import SchedulerAgent
from app.database import async_session_maker
from app.models import Notice
from app.utils.hashing import compute_text_hash

logger = logging.getLogger(__name__)

_notice_agent = NoticeAgent()
_scheduler_agent = SchedulerAgent()


async def route_to_llm_pipeline(messages: list[dict]) -> None:
    """Route raw announcement messages through NoticeAgent → SchedulerAgent.

    Performs deduplication before processing (same as webhook flow).
    """
    for msg in messages:
        raw_text = msg.get("raw_text", "")
        source_group = msg.get("source_group", "VTOP Portal")

        if not raw_text or len(raw_text) < 20:
            continue

        # Deduplication check
        text_hash = compute_text_hash(raw_text)
        async with async_session_maker() as session:
            existing = await session.exec(
                select(Notice).where(Notice.text_hash == text_hash)
            )
            if existing.first() is not None:
                logger.debug("Duplicate VTOP announcement dropped: %s...", raw_text[:40])
                continue

        # Process through LLM pipeline
        try:
            extraction = await _notice_agent.execute({
                "raw_text": raw_text,
                "source_group": source_group,
            })
            await _scheduler_agent.execute(extraction)
            logger.info("VTOP announcement processed: %s", extraction.get("parsed_title"))
        except Exception as e:
            logger.warning("Failed to process VTOP announcement: %s", e)

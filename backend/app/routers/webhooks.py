"""Webhooks router — handles incoming WhatsApp webhook payloads.

Phase 3: Adds hash deduplication and background agent pipeline.
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import async_session_maker, get_session
from app.models import Notice
from app.utils.hashing import compute_text_hash
from app.agents.notice_agent import NoticeAgent
from app.agents.scheduler_agent import SchedulerAgent

logger = logging.getLogger(__name__)

router = APIRouter()

# Resolve backend root (from app/routers/ up to backend/)
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_PAYLOAD_PATH = BACKEND_ROOT / "sample_payload.json"

# Singleton agent instances
_notice_agent = NoticeAgent()
_scheduler_agent = SchedulerAgent()


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Accept a WhatsApp webhook payload, deduplicate, and trigger processing.

    Expected payload shape:
        {"text": "...", "group": "..."}

    Returns immediately with status while agents process in background.
    """
    payload = await request.json()

    # Print payload to console (retained from Phase 1)
    print(payload)

    # Save to sample_payload.json if it doesn't already exist
    if not SAMPLE_PAYLOAD_PATH.exists():
        with open(SAMPLE_PAYLOAD_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    # Extract text and group — handles both Evolution API and test curl formats
    from app.connectors.whatsapp import extract_text_and_group
    raw_text, source_group = extract_text_and_group(payload)

    if not raw_text:
        return {"status": "ignored", "reason": "empty text"}

    # Hash deduplication — check if we've already seen this message
    text_hash = compute_text_hash(raw_text)

    existing = await session.exec(
        select(Notice).where(Notice.text_hash == text_hash)
    )
    if existing.first() is not None:
        return {"status": "duplicate dropped"}

    # New message — kick off the agent pipeline in the background
    asyncio.create_task(
        _run_pipeline(raw_text, source_group),
        name=f"pipeline-{text_hash[:8]}",
    )

    return {"status": "processing"}


async def _run_pipeline(raw_text: str, source_group: str) -> None:
    """Background task: NoticeAgent → SchedulerAgent pipeline."""
    try:
        # Step 1: LLM extraction
        extraction = await _notice_agent.execute({
            "raw_text": raw_text,
            "source_group": source_group,
        })
        logger.info("NoticeAgent extracted: %s", extraction.get("parsed_title"))

        # Step 2: Database insertion with conflict detection
        result = await _scheduler_agent.execute(extraction)
        logger.info(
            "SchedulerAgent inserted notice_id=%s, event_id=%s, task_id=%s, conflict=%s",
            result["notice_id"],
            result["event_id"],
            result["task_id"],
            result["is_conflict"],
        )
    except Exception:
        logger.exception("Pipeline failed for message: %s...", raw_text[:80])

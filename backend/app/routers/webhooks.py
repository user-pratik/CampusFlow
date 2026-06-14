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


@router.post("/webhooks/whatsapp-n8n")
async def receive_whatsapp_n8n(request: Request):
    """Receives WhatsApp messages from n8n/UltraMsg pipeline."""
    import json
    import hashlib
    from datetime import datetime
    from sqlmodel import Session, select as sync_select
    from sqlalchemy import create_engine as sync_create_engine

    from app.connectors.gmail.email_classifier import classify_email
    from app.models import EmailNotification

    body = await request.body()
    body_str = body.decode("utf-8").strip()

    if not body_str:
        return {"status": "error", "detail": "empty body"}

    try:
        payload = json.loads(body_str)
        if isinstance(payload, str):
            payload = json.loads(payload)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    message = payload.get("message", "")
    source = payload.get("source", "WhatsApp Group").lstrip("=")
    sender = payload.get("sender", "").lstrip("=")
    timestamp = payload.get("timestamp", None)

    logger.info("DEBUG whatsapp-n8n: message=%s, source=%s, sender=%s", message[:30], source, sender)

    if not message:
        return {"status": "skipped", "reason": "empty message"}

    result = classify_email(subject=message[:100], sender=source, body=message)

    unique_str = f"{sender}_{timestamp}_{message[:50]}"
    msg_id = f"wa_{hashlib.md5(unique_str.encode()).hexdigest()}"

    # Use sync session for simplicity
    from pathlib import Path
    db_path = Path(__file__).resolve().parent.parent.parent / "campusflow.db"
    engine = sync_create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        existing = db.exec(
            sync_select(EmailNotification).where(EmailNotification.gmail_msg_id == msg_id)
        ).first()

        if existing:
            return {"status": "duplicate", "skipped": True}

        received_at = datetime.utcnow()
        if timestamp:
            try:
                received_at = datetime.fromtimestamp(int(timestamp))
            except (ValueError, TypeError, OSError):
                pass

        notice = EmailNotification(
            gmail_msg_id=msg_id,
            subject=message[:100],
            sender=f"WhatsApp: {source}",
            received_at=received_at,
            category=result["category"],
            priority=result["priority"],
            summary=f"[{sender}] {message[:200]}",
            raw_body=message,
        )
        db.add(notice)
        db.commit()

    logger.info("Stored WhatsApp message from %s: category=%s", source, result["category"])
    return {"status": "stored", "category": result["category"]}


@router.get("/webhooks/whatsapp-groups")
async def get_whatsapp_groups():
    """Returns distinct WhatsApp groups from stored messages with counts."""
    from sqlmodel import Session, select as sync_select
    from sqlalchemy import create_engine as sync_create_engine
    from pathlib import Path
    from app.models import EmailNotification

    db_path = Path(__file__).resolve().parent.parent.parent / "campusflow.db"
    engine = sync_create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        messages = db.exec(
            sync_select(EmailNotification)
            .where(EmailNotification.sender.like("WhatsApp:%"))
            .order_by(EmailNotification.received_at.desc())
        ).all()

    groups: dict = {}
    for m in messages:
        group = (m.sender or "").replace("WhatsApp: ", "")
        if group not in groups:
            groups[group] = {"name": group, "count": 0, "last_message": None, "messages": []}
        groups[group]["count"] += 1
        if len(groups[group]["messages"]) < 15:
            groups[group]["messages"].append({
                "text": m.raw_body or "",
                "sender": (m.summary or "").split("]")[0].replace("[", "") if m.summary else "",
                "category": m.category,
                "date": m.received_at.isoformat() if m.received_at else "",
            })
        if not groups[group]["last_message"]:
            groups[group]["last_message"] = (m.raw_body or "")[:100]

    return list(groups.values())

"""Gmail integration router — email sync, classification, and notifications."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.connectors.gmail.email_classifier import classify_email, classify_emails
from app.connectors.gmail.gmail_client import (
    get_message_detail,
    get_messages,
    is_authenticated,
)
from app.database import get_session
from app.models import EmailNotification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.get("/auth-status")
async def auth_status():
    """Check if Gmail OAuth token exists and is valid."""
    authed = is_authenticated()
    return {"authenticated": authed}


@router.post("/auth")
async def trigger_auth():
    """Trigger Gmail OAuth flow — opens browser for consent."""
    from app.connectors.gmail.gmail_client import authenticate

    creds = authenticate()
    if creds and creds.valid:
        return {"status": "authenticated", "message": "Gmail connected successfully."}
    return {"status": "failed", "message": "OAuth flow did not complete."}


@router.post("/sync")
async def sync_emails(session: AsyncSession = Depends(get_session)):
    """Fetch last 50 emails from Gmail, classify them, and store in DB.
    
    Also reclassifies ALL existing emails with the current classifier rules
    to ensure stale classifications from old logic are corrected.
    """
    if not is_authenticated():
        return {"status": "not_authenticated", "message": "Run POST /api/gmail/auth first."}

    messages = get_messages(max_results=50, query="")
    if not messages:
        return {"status": "no_messages", "synced": 0}

    existing_ids_result = await session.exec(
        select(EmailNotification.gmail_msg_id)
    )
    existing_ids = set(existing_ids_result.all())

    new_msg_ids = [m["id"] for m in messages if m["id"] not in existing_ids]

    # --- Fetch and store NEW emails ---
    stored_count = 0
    if new_msg_ids:
        email_details = []
        for msg_id in new_msg_ids[:50]:
            detail = get_message_detail(msg_id)
            if detail:
                email_details.append(detail)

        if email_details:
            classifications = classify_emails(email_details)

            for detail, classification in zip(email_details, classifications):
                received_at = datetime.utcnow()
                if detail.get("date"):
                    try:
                        received_at = datetime.fromisoformat(detail["date"])
                    except (ValueError, TypeError):
                        pass

                notification = EmailNotification(
                    gmail_msg_id=detail["msg_id"],
                    subject=detail.get("subject", "(No Subject)"),
                    sender=detail.get("sender", "Unknown"),
                    received_at=received_at,
                    category=classification["category"],
                    priority=classification["priority"],
                    summary=classification["summary"],
                    is_read=False,
                    raw_body=detail.get("body_text", "")[:10000],
                )
                session.add(notification)
                stored_count += 1

    # --- Reclassify ALL existing emails with current logic ---
    reclassified = 0
    existing_result = await session.exec(select(EmailNotification))
    existing_emails = existing_result.all()
    for email in existing_emails:
        classification = classify_email(
            email.subject or "",
            email.sender or "",
            email.raw_body or "",
        )
        if (email.category != classification["category"]
                or email.priority != classification["priority"]):
            email.category = classification["category"]
            email.priority = classification["priority"]
            email.summary = classification["summary"]
            session.add(email)
            reclassified += 1

    await session.commit()
    logger.info("Synced %d new emails, reclassified %d existing.", stored_count, reclassified)

    return {
        "status": "synced",
        "synced": stored_count,
        "reclassified": reclassified,
        "total_fetched": len(messages),
        "already_stored": len(existing_ids),
    }


@router.get("/notifications")
async def get_notifications(session: AsyncSession = Depends(get_session)):
    """Return high-priority email notifications."""
    result = await session.exec(
        select(EmailNotification)
        .where(EmailNotification.priority == "high")
        .order_by(EmailNotification.received_at.desc())
        .limit(50)
    )
    return result.all()


@router.get("/all")
async def get_all_emails(
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Return all emails with real-time reclassification applied.
    
    Re-runs the classifier on each email to ensure the latest rules are used,
    regardless of what was stored in the DB from a previous sync.
    """
    stmt = select(EmailNotification).order_by(EmailNotification.received_at.desc()).limit(limit * 2 if category else limit)
    result = await session.exec(stmt)
    emails = result.all()

    # Reclassify in real-time and update DB if changed
    output = []
    dirty = False
    for email in emails:
        classification = classify_email(
            email.subject or "",
            email.sender or "",
            email.raw_body or "",
        )
        if (email.category != classification["category"]
                or email.priority != classification["priority"]):
            email.category = classification["category"]
            email.priority = classification["priority"]
            email.summary = classification["summary"]
            session.add(email)
            dirty = True

        # Apply category filter AFTER reclassification
        if category and email.category != category.upper():
            continue
        output.append(email)

    if dirty:
        await session.commit()

    return output[:limit]


@router.post("/mark-read/{msg_id}")
async def mark_read(msg_id: str, session: AsyncSession = Depends(get_session)):
    """Mark an email notification as read."""
    result = await session.exec(
        select(EmailNotification).where(EmailNotification.gmail_msg_id == msg_id)
    )
    notification = result.first()
    if not notification:
        return {"status": "not_found"}
    notification.is_read = True
    session.add(notification)
    await session.commit()
    return {"status": "marked_read"}


@router.post("/reclassify")
async def reclassify_all(session: AsyncSession = Depends(get_session)):
    """Re-classify all existing emails using current classifier rules."""
    result = await session.exec(select(EmailNotification))
    emails = result.all()

    for email in emails:
        classification = classify_email(
            email.subject or "",
            email.sender or "",
            email.raw_body or "",
        )
        email.category = classification["category"]
        email.priority = classification["priority"]
        email.summary = classification["summary"]
        session.add(email)

    await session.commit()
    logger.info("Reclassified %d emails.", len(emails))
    return {"reclassified": len(emails)}


@router.delete("/clear")
async def clear_all_emails(session: AsyncSession = Depends(get_session)):
    """Delete all stored email notifications so they can be re-fetched with updated classification."""
    result = await session.exec(select(EmailNotification))
    emails = result.all()
    count = len(emails)
    for email in emails:
        await session.delete(email)
    await session.commit()
    logger.info("Cleared %d emails from database.", count)
    return {"status": "cleared", "deleted": count}


# ─── Calendar Integration ─────────────────────────────────────────────────────

from pydantic import BaseModel as _BaseModel


class CreateEventRequest(_BaseModel):
    title: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    description: str = ""
    location: str = ""
    duration_hours: int = 1


@router.post("/create-event")
async def create_event(body: CreateEventRequest):
    """Create a Google Calendar event."""
    from app.connectors.gmail.calendar_client import create_calendar_event

    result = create_calendar_event(
        title=body.title,
        date=body.date,
        time=body.time,
        description=body.description,
        location=body.location,
        duration_hours=body.duration_hours,
    )
    return result


@router.get("/calendar-events")
async def get_calendar_events():
    """List upcoming Google Calendar events."""
    from app.connectors.gmail.calendar_client import list_upcoming_events

    events = list_upcoming_events(max_results=15)
    return {"events": events}


@router.get("/emails-only")
async def get_emails_only(
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Return only Gmail emails (excludes WhatsApp messages)."""
    stmt = (
        select(EmailNotification)
        .where(~EmailNotification.sender.like("WhatsApp:%"))
        .order_by(EmailNotification.received_at.desc())
        .limit(limit)
    )
    if category:
        stmt = stmt.where(EmailNotification.category == category.upper())
    result = await session.exec(stmt)
    return result.all()


@router.get("/whatsapp-only")
async def get_whatsapp_only(
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Return only WhatsApp messages (sender starts with 'WhatsApp:')."""
    result = await session.exec(
        select(EmailNotification)
        .where(EmailNotification.sender.like("WhatsApp:%"))
        .order_by(EmailNotification.received_at.desc())
        .limit(limit)
    )
    return result.all()

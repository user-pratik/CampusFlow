"""Email context builder for the chat agent.

Fetches emails from DB and formats them as context string for LLM consumption.
"""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import EmailNotification


async def get_email_context(session: AsyncSession, max_emails: int = 30) -> str:
    """Build a formatted context string of recent emails for LLM consumption.

    Args:
        session: Async database session.
        max_emails: Maximum number of emails to include.

    Returns:
        Formatted string of recent emails with metadata.
    """
    result = await session.exec(
        select(EmailNotification)
        .order_by(EmailNotification.received_at.desc())
        .limit(max_emails)
    )
    emails = result.all()

    if not emails:
        return "No emails in inbox."

    lines = []
    for e in emails:
        status = "📩 UNREAD" if not e.is_read else "📧"
        lines.append(
            f"{status} From: {e.sender}\n"
            f"  Subject: {e.subject}\n"
            f"  Date: {e.received_at.strftime('%Y-%m-%d %H:%M') if e.received_at else 'Unknown'}\n"
            f"  Category: {e.category} | Priority: {e.priority}\n"
            f"  Summary: {e.summary}\n"
            f"  Body: {e.raw_body[:400] if e.raw_body else 'No body'}"
        )
    return "\n\n".join(lines)


async def get_email_context_list(session: AsyncSession, max_emails: int = 30) -> list[dict]:
    """Get emails as a list of dicts for structured context.

    Args:
        session: Async database session.
        max_emails: Maximum number of emails to include.

    Returns:
        List of email dicts.
    """
    result = await session.exec(
        select(EmailNotification)
        .order_by(EmailNotification.received_at.desc())
        .limit(max_emails)
    )
    emails = result.all()

    return [
        {
            "from": e.sender,
            "subject": e.subject,
            "date": e.received_at.isoformat() if e.received_at else "",
            "category": e.category,
            "priority": e.priority,
            "summary": e.summary,
            "body": e.raw_body[:500] if e.raw_body else "",
            "is_read": e.is_read,
        }
        for e in emails
    ]

"""Notifications router — list and mark-read for agent-generated notifications."""

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Notification

router = APIRouter()


@router.get("/notifications")
async def get_notifications(
    unread_only: bool = Query(default=False, description="If true, return only unread notifications"),
    session: AsyncSession = Depends(get_session),
):
    """Return notifications, newest first. Optionally filter to unread only."""
    query = select(Notification).order_by(Notification.created_at.desc())
    if unread_only:
        query = query.where(Notification.is_read == False)  # noqa: E712

    result = await session.exec(query)
    notifications = result.all()

    return {
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "source_agent": n.source_agent,
                "priority": n.priority,
                "is_read": n.is_read,
                "link": n.link,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
        "unread_count": sum(1 for n in notifications if not n.is_read),
        "total": len(notifications),
    }


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Mark a single notification as read."""
    result = await session.exec(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.first()

    if notification is None:
        return {"error": "Notification not found", "id": notification_id}

    notification.is_read = True
    session.add(notification)
    await session.commit()

    return {"status": "ok", "id": notification_id, "is_read": True}

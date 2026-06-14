"""Google Calendar client for CampusFlow.

Creates calendar events using the authenticated Google OAuth credentials.
"""

import logging
from typing import Optional

from googleapiclient.discovery import build

from app.connectors.gmail.gmail_client import authenticate

logger = logging.getLogger(__name__)


def create_calendar_event(
    title: str,
    date: str,
    time: str,
    description: str = "",
    location: str = "",
    duration_hours: int = 1,
) -> dict:
    """Create a Google Calendar event.

    Args:
        title: Event title/summary.
        date: Date in YYYY-MM-DD format.
        time: Start time in HH:MM format (24h).
        description: Event description.
        location: Event location.
        duration_hours: Duration in hours (default 1).

    Returns:
        Dict with event_id and htmlLink, or error.
    """
    creds = authenticate()
    if not creds:
        return {"error": "Not authenticated. Run POST /api/gmail/auth first."}

    try:
        service = build("calendar", "v3", credentials=creds)

        # Calculate end time
        start_hour = int(time[:2])
        start_min = time[3:5] if len(time) >= 5 else "00"
        end_hour = start_hour + duration_hours
        end_time = f"{str(end_hour).zfill(2)}:{start_min}"

        event = {
            "summary": title,
            "location": location,
            "description": description,
            "start": {
                "dateTime": f"{date}T{time}:00",
                "timeZone": "Asia/Kolkata",
            },
            "end": {
                "dateTime": f"{date}T{end_time}:00",
                "timeZone": "Asia/Kolkata",
            },
        }

        result = service.events().insert(calendarId="primary", body=event).execute()
        logger.info("Created calendar event: %s on %s at %s", title, date, time)

        return {
            "event_id": result["id"],
            "link": result.get("htmlLink", ""),
            "title": title,
            "date": date,
            "time": time,
        }

    except Exception as e:
        logger.error("Failed to create calendar event: %s", e)
        return {"error": str(e)}


def list_upcoming_events(max_results: int = 10) -> list[dict]:
    """List upcoming calendar events.

    Args:
        max_results: Maximum number of events to return.

    Returns:
        List of event dicts with title, start, end, location.
    """
    creds = authenticate()
    if not creds:
        return []

    try:
        from datetime import datetime, timezone

        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc).isoformat()

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = []
        for event in result.get("items", []):
            start = event["start"].get("dateTime", event["start"].get("date", ""))
            end = event["end"].get("dateTime", event["end"].get("date", ""))
            events.append({
                "title": event.get("summary", "(No title)"),
                "start": start,
                "end": end,
                "location": event.get("location", ""),
                "description": event.get("description", ""),
                "link": event.get("htmlLink", ""),
            })

        return events

    except Exception as e:
        logger.error("Failed to list calendar events: %s", e)
        return []

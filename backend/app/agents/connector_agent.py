"""Connector Agent — Handles WhatsApp, Email, and Calendar queries.

This agent acts as if it has direct access to the student's:
- WhatsApp groups (subject groups, batch groups, clubs)
- Email inbox (VIT emails, placement, hackathon)
- Calendar (exams, deadlines, meetings)

It uses fabricated data from backend/data/fabricated/ to simulate real access.
When real integrations are live, this agent swaps to real data sources.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from app.agents.base import BaseAgent
from app.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

# Load fabricated data
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fabricated"


def _load_json(filename: str) -> dict:
    """Load a fabricated data file."""
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


CONNECTOR_SYSTEM_PROMPT = """\
You are CampusFlow's Communication & Calendar agent for {name}, a {branch} student at {college}.

You have DIRECT ACCESS to their WhatsApp groups, email inbox, and calendar. You can see all their 
messages, emails, and upcoming events. Answer as if you are reading their phone right now.

IMPORTANT BEHAVIOR:
- When asked about a subject group, find messages from that group and summarize them naturally
- When asked "any new messages?", show the most recent/important ones across all groups
- When asked about study groups, check if anyone in their subject group has proposed one
- When asked about emails, show relevant unread or important emails
- When asked about calendar/schedule, show upcoming events and deadlines
- Be specific — mention sender names, exact dates, exact content
- Don't say "I don't have access" — you DO have access to everything below
- If someone in a group offered to form a study group, mention that specifically
- Sound natural, like you're looking at their phone: "I see a message from Prof. Venkatesh in your Embedded Systems group..."

WHATSAPP GROUPS THE STUDENT IS PART OF:
{whatsapp_groups}

RECENT WHATSAPP MESSAGES:
{whatsapp_messages}

EMAIL INBOX:
{emails}

CALENDAR & UPCOMING EVENTS:
{calendar}

TIMETABLE:
{timetable}

OFFICIAL ACADEMIC CALENDAR (VIT):
{academic_calendar}

CONVERSATION HISTORY:
{history}

TODAY: {today}
"""


class ConnectorAgent(BaseAgent):
    """Handles queries about WhatsApp messages, emails, and calendar events."""

    def __init__(self):
        self._whatsapp_data = _load_json("whatsapp_groups.json")
        self._email_data = _load_json("emails.json")
        self._calendar_data = _load_json("calendar.json")
        self._regulations = _load_json("academic_regulations.json")

    async def execute(self, payload: dict) -> dict:
        """Process a WhatsApp/Email/Calendar query.

        Args:
            payload: {
                "user_message": str,
                "sub_intent": str,
                "context": dict,
                "history": list[dict],
                "profile": dict
            }

        Returns:
            {
                "response": str,
                "actions": list[dict],
                "panel": str | None,
                "panel_data": dict | None
            }
        """
        user_message = payload["user_message"]
        history = payload["history"]
        profile = payload["profile"]
        sub_intent = payload.get("sub_intent", "")
        context = payload.get("context", {})

        # Build context strings
        whatsapp_groups = self._format_groups()
        whatsapp_messages = self._format_messages(user_message)
        emails = self._format_emails(user_message, context.get("emails"))
        calendar = self._format_calendar()
        timetable = self._format_timetable()
        academic_calendar = self._format_academic_calendar()

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:300]}" for m in history[-8:]
        ) if history else "No prior conversation."

        system_prompt = CONNECTOR_SYSTEM_PROMPT.format(
            name=profile.get("name", "Student"),
            branch=profile.get("branch", "CS"),
            college=profile.get("college", "VIT"),
            whatsapp_groups=whatsapp_groups,
            whatsapp_messages=whatsapp_messages,
            emails=emails,
            calendar=calendar,
            timetable=timetable,
            academic_calendar=academic_calendar,
            history=history_text,
            today=datetime.now().strftime("%A, %B %d, %Y"),
        )

        try:
            response = await chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.5,
                max_tokens=1024,
            )
        except Exception as e:
            logger.warning("ConnectorAgent LLM call failed: %s", e)
            response = "I'm having trouble accessing your messages right now. Try again in a moment."

        # Determine panel and actions
        panel, actions = self._determine_response_type(user_message, sub_intent)

        # Include structured data for frontend widgets
        panel_data = self._build_panel_data(user_message, sub_intent)

        return {
            "response": response,
            "actions": actions,
            "panel": panel,
            "panel_data": panel_data,
        }

    def _format_groups(self) -> str:
        """Format WhatsApp groups list."""
        groups = self._whatsapp_data.get("groups", [])
        lines = []
        for g in groups:
            lines.append(f"- {g['name']} ({g['type']}, {g['members']} members)")
        return "\n".join(lines)

    def _format_messages(self, query: str) -> str:
        """Format WhatsApp messages, prioritizing relevant ones based on query."""
        messages = self._whatsapp_data.get("messages", [])
        q = query.lower()

        # If query mentions a specific subject, filter for that group
        relevant = []
        all_messages = sorted(messages, key=lambda m: m["timestamp"], reverse=True)

        # Check if query mentions a specific subject/group
        subject_keywords = {
            "embedded": "bcse305l",
            "compiler": "bcse307l",
            "os": "bcse302l",
            "operating system": "bcse302l",
            "probability": "bmat301l",
            "statistics": "bmat301l",
            "network": "bcse309l",
            "cn": "bcse309l",
            "dbms": "bcse304l",
            "database": "bcse304l",
            "placement": "placement-cell",
            "hackathon": "hackathon-club",
            "ml": "ml-study",
            "machine learning": "ml-study",
            "cp": "cp-vit",
            "competitive": "cp-vit",
        }

        target_group = None
        for keyword, group_id in subject_keywords.items():
            if keyword in q:
                target_group = group_id
                break

        if target_group:
            relevant = [m for m in all_messages if m["group_id"] == target_group]
        else:
            # Show most recent important messages
            relevant = [m for m in all_messages if m.get("is_important")][:8]
            if len(relevant) < 5:
                relevant = all_messages[:10]

        lines = []
        for m in relevant[:10]:
            faculty_tag = " [FACULTY]" if m.get("sender_type") == "faculty" else ""
            important_tag = " ⚠️" if m.get("is_important") else ""
            lines.append(
                f"[{m['group_name']}] {m['sender']}{faculty_tag}{important_tag} ({m['timestamp'][:10]}):\n"
                f"  \"{m['text']}\""
            )
        return "\n\n".join(lines) if lines else "No recent messages."

    def _format_emails(self, query: str, db_emails: list[dict] | None = None) -> str:
        """Format emails, using real DB emails if available, falling back to fabricated data."""
        q = query.lower()

        # Use real emails from DB if available
        if db_emails:
            # Filter based on query keywords
            if "unread" in q:
                filtered = [e for e in db_emails if not e.get("is_read")]
            elif "placement" in q or "job" in q or "intern" in q or "cdc" in q:
                filtered = [e for e in db_emails if e.get("category") == "PLACEMENT"]
            elif "exam" in q or "result" in q or "marks" in q:
                filtered = [e for e in db_emails if e.get("category") == "EXAM"]
            elif "fee" in q or "payment" in q:
                filtered = [e for e in db_emails if e.get("category") == "FEE"]
            elif "event" in q or "fest" in q or "workshop" in q:
                filtered = [e for e in db_emails if e.get("category") == "EVENT"]
            else:
                filtered = db_emails[:10]

            lines = []
            for e in filtered[:10]:
                status = "📩 UNREAD" if not e.get("is_read") else "📧"
                lines.append(
                    f"{status} From: {e.get('from', 'Unknown')}\n"
                    f"  Subject: {e.get('subject', 'No subject')}\n"
                    f"  Date: {e.get('date', '')[:10]}\n"
                    f"  Category: {e.get('category', '?')} | Priority: {e.get('priority', '?')}\n"
                    f"  Summary: {e.get('summary', '')}\n"
                    f"  Body: {e.get('body', '')[:400]}"
                )
            return "\n\n".join(lines) if lines else "No matching emails found."

        # Fallback to fabricated data
        emails = self._email_data.get("emails", [])

        # Filter based on query keywords
        if "unread" in q:
            filtered = [e for e in emails if not e["read"]]
        elif "placement" in q or "job" in q or "intern" in q:
            filtered = [e for e in emails if e["category"] == "placement"]
        elif "hackathon" in q or "amazon" in q:
            filtered = [e for e in emails if "hackathon" in e.get("category", "")]
        else:
            # Show most recent, prioritize unread and starred
            filtered = sorted(
                emails,
                key=lambda e: (not e["read"], e.get("starred", False), e["timestamp"]),
                reverse=True,
            )[:6]

        lines = []
        for e in filtered[:6]:
            status = "📩 UNREAD" if not e["read"] else "📧"
            star = " ⭐" if e.get("starred") else ""
            lines.append(
                f"{status}{star} From: {e['from_name']} <{e['from']}>\n"
                f"  Subject: {e['subject']}\n"
                f"  Preview: {e['preview']}\n"
                f"  Date: {e['timestamp'][:10]}"
            )
        return "\n\n".join(lines) if lines else "No relevant emails."

    def _format_calendar(self) -> str:
        """Format upcoming calendar events."""
        events = self._calendar_data.get("events", [])
        # Sort by date, show upcoming ones
        sorted_events = sorted(events, key=lambda e: e["date"])

        lines = []
        for e in sorted_events[:10]:
            icon = {"exam": "📝", "deadline": "⏰", "meeting": "👥", "event": "📌"}.get(
                e["type"], "📌"
            )
            course = f" [{e['course_code']}]" if e.get("course_code") else ""
            lines.append(
                f"{icon}{course} {e['title']}\n"
                f"  Date: {e['date']} | Time: {e['start_time']} - {e['end_time']}\n"
                f"  Location: {e['location']}\n"
                f"  Notes: {e.get('notes', 'None')}"
            )
        return "\n\n".join(lines)

    def _format_timetable(self) -> str:
        """Format today's timetable."""
        timetable = self._calendar_data.get("timetable", {})
        today = datetime.now().strftime("%A")
        today_schedule = timetable.get(today, [])

        if not today_schedule:
            return f"No classes today ({today})."

        lines = [f"Today ({today}):"]
        for cls in today_schedule:
            lines.append(
                f"  {cls['time']} — {cls['course_title']} ({cls['course_code']}) "
                f"| {cls['type']} | Room: {cls['room']} | Faculty: {cls['faculty']}"
            )
        return "\n".join(lines)

    def _format_academic_calendar(self) -> str:
        """Format official VIT academic calendar dates."""
        cal = self._regulations.get("calendar", {})
        if not cal:
            return "No academic calendar data."

        lines = [
            f"Semester: {cal.get('semester', 'N/A')}",
            f"CAT-1: {cal.get('cat1_exams', {}).get('start', '?')} to {cal.get('cat1_exams', {}).get('end', '?')}",
            f"CAT-2: {cal.get('cat2_exams', {}).get('start', '?')} to {cal.get('cat2_exams', {}).get('end', '?')}",
            f"Course Withdrawal: {cal.get('course_withdrawal_window', {}).get('start', '?')} to {cal.get('course_withdrawal_window', {}).get('end', '?')}",
            f"Last Instructional Day (Labs): {cal.get('last_instructional_day_labs', '?')}",
            f"Last Instructional Day (Theory): {cal.get('last_instructional_day_theory', '?')}",
            f"FAT Labs: {cal.get('fat_exams_labs', {}).get('start', '?')} to {cal.get('fat_exams_labs', {}).get('end', '?')}",
            f"FAT Theory Begins: {cal.get('fat_exams_theory_begins', '?')}",
            f"Summer Sem: {cal.get('summer_semester_start', '?')}",
            f"Fall 2026-27: {cal.get('fall_2026_27_start', '?')}",
        ]
        return "\n".join(lines)

    def _determine_response_type(self, message: str, sub_intent: str) -> tuple:
        """Determine which panel to suggest and what actions to offer."""
        q = message.lower()

        if any(w in q for w in ["whatsapp", "message", "group", "chat", "study group"]):
            return "whatsapp", [
                {"label": "Open WhatsApp panel", "type": "navigate", "payload": "whatsapp"},
                {"label": "Reply in group", "type": "reply"},
                {"label": "Set reminder for this", "type": "reply"},
            ]
        elif any(w in q for w in ["email", "mail", "inbox"]):
            return "email", [
                {"label": "Open email panel", "type": "navigate", "payload": "email"},
                {"label": "Draft reply", "type": "reply"},
                {"label": "Mark as read", "type": "reply"},
            ]
        elif any(w in q for w in ["calendar", "schedule", "exam", "deadline", "upcoming", "due", "timetable", "class", "today", "tomorrow", "tonight"]):
            return "calendar", [
                {"label": "Show calendar", "type": "navigate", "payload": "calendar"},
                {"label": "Set reminder", "type": "reply"},
                {"label": "Add to study plan", "type": "reply"},
            ]
        else:
            return None, [
                {"label": "Check messages", "type": "navigate", "payload": "whatsapp"},
                {"label": "Show calendar", "type": "navigate", "payload": "calendar"},
            ]

    def _build_panel_data(self, message: str, sub_intent: str) -> dict | None:
        """Build structured data for frontend widgets."""
        q = message.lower()

        # Calendar widget data
        if any(w in q for w in ["calendar", "schedule", "exam", "deadline", "upcoming", "due", "week", "today", "tomorrow", "tonight"]):
            events = self._calendar_data.get("events", [])
            today_str = datetime.now().strftime("%Y-%m-%d")

            # If asking about "today", filter to today's events
            if "today" in q or "tonight" in q:
                filtered = [e for e in events if e["date"] == today_str]
                # If no events today, still return the list (empty widget won't render)
                sorted_events = sorted(filtered, key=lambda e: e["start_time"])
            else:
                sorted_events = sorted(events, key=lambda e: e["date"])

            return {
                "calendar_events": [
                    {
                        "title": e["title"],
                        "date": e["date"],
                        "start_time": e["start_time"],
                        "end_time": e.get("end_time", ""),
                        "location": e["location"],
                        "type": e["type"],
                        "course_code": e.get("course_code"),
                        "notes": e.get("notes", ""),
                    }
                    for e in sorted_events[:12]
                ]
            }

        return None

"""Deadline Aggregator Agent — extracts deadlines from Gmail emails and manual calendar data.

Sources:
1. Gmail: scans EmailNotification records with category FEE/PLACEMENT/EXAM,
   uses Groq LLM to extract due dates + titles, upserts Deadline rows.
2. Manual: reads academic_regulations.json (calendar section) and/or
   deadlines_manual.json for hand-curated entries.

No Moodle assignments in this version.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import async_session_maker
from app.models import Deadline, EmailNotification
from app.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
FABRICATED_DIR = DATA_DIR / "fabricated"

# Categories from Gmail emails that likely contain deadlines
DEADLINE_EMAIL_CATEGORIES = {"FEE", "PLACEMENT", "EXAM"}


# ─── Gmail Deadline Extraction ────────────────────────────────────────────────


async def extract_deadlines_from_emails() -> list[dict]:
    """Scan EmailNotification records for deadline-relevant categories,
    use Groq LLM to extract due date + title, and upsert Deadline rows.

    Returns:
        List of dicts summarizing extracted deadlines.
    """
    extracted: list[dict] = []

    async with async_session_maker() as session:
        # Get emails with categories that typically contain deadlines
        result = await session.exec(
            select(EmailNotification).where(
                EmailNotification.category.in_(DEADLINE_EMAIL_CATEGORIES)
            )
        )
        emails = result.all()

        if not emails:
            logger.info("No deadline-relevant emails found.")
            return extracted

        # Check which gmail_msg_ids already have deadline entries (skip duplicates)
        existing_result = await session.exec(
            select(Deadline.source_ref_id).where(Deadline.source == "gmail")
        )
        existing_refs = set(existing_result.all())

        # Filter to unprocessed emails
        new_emails = [e for e in emails if e.gmail_msg_id not in existing_refs]

        if not new_emails:
            logger.info("All %d deadline emails already processed.", len(emails))
            return extracted

        logger.info("Processing %d new deadline-relevant emails.", len(new_emails))

        # Batch emails for LLM extraction (process in groups of 5)
        for batch_start in range(0, len(new_emails), 5):
            batch = new_emails[batch_start:batch_start + 5]
            batch_results = await _extract_batch(batch)

            for deadline_info in batch_results:
                # Upsert deadline
                deadline = Deadline(
                    source="gmail",
                    title=deadline_info["title"],
                    due_datetime=deadline_info["due_datetime"],
                    category=deadline_info["category"],
                    status="upcoming",
                    source_ref_id=deadline_info["source_ref_id"],
                )
                session.add(deadline)
                extracted.append({
                    "title": deadline_info["title"],
                    "due": deadline_info["due_datetime"].isoformat(),
                    "category": deadline_info["category"],
                    "source": "gmail",
                })

        await session.commit()

    logger.info("Extracted %d deadlines from emails.", len(extracted))

    # Sync new deadlines to Google Calendar
    await sync_deadlines_to_calendar()

    return extracted


async def _extract_batch(emails: list[EmailNotification]) -> list[dict]:
    """Use Groq LLM to extract deadline info from a batch of emails.

    Returns:
        List of dicts with: title, due_datetime, category, source_ref_id
    """
    # Build prompt with email summaries
    email_texts = []
    for i, email in enumerate(emails):
        text = (
            f"[Email {i+1}] (msg_id: {email.gmail_msg_id})\n"
            f"Subject: {email.subject or 'N/A'}\n"
            f"From: {email.sender or 'N/A'}\n"
            f"Category: {email.category}\n"
            f"Date: {email.received_at.isoformat() if email.received_at else 'N/A'}\n"
            f"Summary: {email.summary or ''}\n"
            f"Body excerpt: {(email.raw_body or '')[:500]}\n"
        )
        email_texts.append(text)

    prompt = f"""Extract deadlines from these college emails. For each email that contains a deadline or due date, output a JSON array of objects.

Each object should have:
- "msg_id": the msg_id from the email header
- "title": short deadline title (e.g. "Fee Payment Due", "Amazon Placement Test")
- "due_date": ISO format datetime (YYYY-MM-DDTHH:MM:SS), best guess if only date is given use 23:59:00
- "category": one of "fee", "placement", "exam", "event"

If an email has no clear deadline/due date, skip it.
Today's date: {datetime.now().strftime("%Y-%m-%d")}

EMAILS:
{"".join(email_texts)}

Respond ONLY with a JSON array. If no deadlines found, respond with [].
"""

    try:
        response = await chat_completion(
            messages=[
                {"role": "system", "content": "You extract deadline dates from college emails. Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        # Parse response
        data = json.loads(response)
        # Handle both {"deadlines": [...]} and [...] formats
        if isinstance(data, dict):
            items = data.get("deadlines", data.get("results", []))
        elif isinstance(data, list):
            items = data
        else:
            items = []

        results = []
        for item in items:
            try:
                due_str = item.get("due_date", "")
                due_dt = datetime.fromisoformat(due_str) if due_str else None
                if due_dt is None:
                    continue

                results.append({
                    "title": item.get("title", "Untitled Deadline"),
                    "due_datetime": due_dt,
                    "category": item.get("category", "event"),
                    "source_ref_id": item.get("msg_id", ""),
                })
            except (ValueError, TypeError):
                continue

        return results

    except Exception as e:
        logger.warning("LLM extraction failed for email batch: %s", e)
        return []


# ─── Manual Deadline Loading ──────────────────────────────────────────────────


async def load_manual_deadlines() -> list[dict]:
    """Load deadlines from manual sources:
    1. academic_regulations.json (calendar section with exam dates, withdrawal windows)
    2. deadlines_manual.json (hand-curated deadline entries)

    Upserts Deadline rows with source="manual", deduplicating on source_ref_id.

    Returns:
        List of dicts summarizing loaded deadlines.
    """
    loaded: list[dict] = []
    entries: list[dict] = []

    # Source 1: academic_regulations.json → calendar section
    reg_file = FABRICATED_DIR / "academic_regulations.json"
    if reg_file.exists():
        try:
            with open(reg_file, "r", encoding="utf-8") as f:
                regulations = json.load(f)
            calendar = regulations.get("calendar", {})
            entries.extend(_extract_from_academic_calendar(calendar))
            logger.info("Loaded %d entries from academic_regulations.json calendar.", len(entries))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read academic_regulations.json: %s", e)

    # Source 2: deadlines_manual.json (direct entry format)
    manual_file = DATA_DIR / "deadlines_manual.json"
    if manual_file.exists():
        try:
            with open(manual_file, "r", encoding="utf-8") as f:
                manual_data = json.load(f)
            # Expected format: [{"title": "...", "due_date": "YYYY-MM-DD", "category": "..."}, ...]
            items = manual_data if isinstance(manual_data, list) else manual_data.get("deadlines", [])
            for item in items:
                due_str = item.get("due_date") or item.get("due_datetime") or item.get("date")
                if not due_str:
                    continue
                try:
                    # Parse various date formats
                    if "T" in due_str:
                        due_dt = datetime.fromisoformat(due_str)
                    else:
                        due_dt = datetime.strptime(due_str, "%Y-%m-%d").replace(hour=23, minute=59)
                except ValueError:
                    continue

                ref_id = f"manual_{item.get('title', '')[:30]}_{due_str}"
                entries.append({
                    "title": item.get("title", "Manual Deadline"),
                    "due_datetime": due_dt,
                    "category": item.get("category", "academic"),
                    "source_ref_id": ref_id,
                })
            logger.info("Loaded %d entries from deadlines_manual.json.", len(items))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read deadlines_manual.json: %s", e)

    if not entries:
        logger.info("No manual deadline sources found.")
        return loaded

    # Upsert to database (deduplicate on source_ref_id)
    async with async_session_maker() as session:
        existing_result = await session.exec(
            select(Deadline.source_ref_id).where(Deadline.source == "manual")
        )
        existing_refs = set(existing_result.all())

        new_entries = [e for e in entries if e["source_ref_id"] not in existing_refs]

        for entry in new_entries:
            session.add(Deadline(
                source="manual",
                title=entry["title"],
                due_datetime=entry["due_datetime"],
                category=entry["category"],
                status="upcoming",
                source_ref_id=entry["source_ref_id"],
            ))
            loaded.append({
                "title": entry["title"],
                "due": entry["due_datetime"].isoformat(),
                "category": entry["category"],
                "source": "manual",
            })

        await session.commit()

    logger.info("Upserted %d new manual deadlines.", len(loaded))

    # Sync new deadlines to Google Calendar
    await sync_deadlines_to_calendar()

    return loaded


def _extract_from_academic_calendar(calendar: dict) -> list[dict]:
    """Extract deadline entries from the academic_regulations.json calendar structure.

    Expected keys: cat1_exams, cat2_exams, fat_exams_labs, fat_exams_theory_begins,
    course_withdrawal_window, last_instructional_day_labs, last_instructional_day_theory, etc.
    """
    entries: list[dict] = []
    year = datetime.now().year

    # Map calendar keys to deadline entries
    mappings = [
        ("cat1_exams", "start", "CAT-1 Exams Begin", "exam"),
        ("cat2_exams", "start", "CAT-2 Exams Begin", "exam"),
        ("fat_exams_labs", "start", "FAT Lab Exams Begin", "exam"),
        ("fat_exams_theory_begins", None, "FAT Theory Exams Begin", "exam"),
        ("course_withdrawal_window", "end", "Course Withdrawal Deadline", "academic"),
        ("last_instructional_day_labs", None, "Last Lab Day", "academic"),
        ("last_instructional_day_theory", None, "Last Theory Day", "academic"),
        ("summer_semester_start", None, "Summer Semester Begins", "academic"),
        ("fall_2026_27_start", None, "Fall 2026-27 Begins", "academic"),
    ]

    for key, sub_key, title, category in mappings:
        value = calendar.get(key)
        if value is None:
            continue

        date_str = value.get(sub_key) if isinstance(value, dict) and sub_key else value
        if not isinstance(date_str, str):
            continue

        due_dt = _parse_calendar_date(date_str, year)
        if due_dt is None:
            continue

        ref_id = f"acad_cal_{key}_{sub_key or 'val'}"
        entries.append({
            "title": title,
            "due_datetime": due_dt,
            "category": category,
            "source_ref_id": ref_id,
        })

    return entries


def _parse_calendar_date(date_str: str, default_year: int) -> datetime | None:
    """Parse various date string formats from the academic calendar.

    Supports: "2026-01-15", "15 Jan 2026", "Jan 15, 2026", "15/01/2026", etc.
    """
    from dateutil import parser as dateutil_parser

    try:
        dt = dateutil_parser.parse(date_str, dayfirst=False)
        return dt.replace(hour=9, minute=0, second=0)
    except (ValueError, TypeError):
        pass

    return None


# ─── Moodle Deadline Extraction ───────────────────────────────────────────────


async def fetch_moodle_deadlines() -> list[dict]:
    """Fetch upcoming assignments from Moodle and upsert as Deadline rows.

    Uses the Moodle connector to get assignments, creates Deadline entries
    with source="moodle". Deduplicates on source_ref_id (moodle_assign_{id}).

    Returns:
        List of dicts summarizing extracted deadlines.
    """
    from app.connectors.moodle.moodle_client import get_upcoming_assignments

    loaded: list[dict] = []

    assignments = await get_upcoming_assignments()
    if not assignments:
        logger.info("No Moodle assignments found (or Moodle not configured).")
        return loaded

    async with async_session_maker() as session:
        # Check existing moodle deadlines
        existing_result = await session.exec(
            select(Deadline.source_ref_id).where(Deadline.source == "moodle")
        )
        existing_refs = set(existing_result.all())

        for assign in assignments:
            ref_id = f"moodle_assign_{assign['moodle_assign_id']}"
            if ref_id in existing_refs:
                continue

            title = f"{assign['assignment_name']}"
            if assign.get("course_code"):
                title = f"[{assign['course_code']}] {title}"

            session.add(Deadline(
                source="moodle",
                title=title,
                due_datetime=assign["due_date"],
                category="assignment",
                status="upcoming",
                source_ref_id=ref_id,
            ))
            loaded.append({
                "title": title,
                "due": assign["due_date"].isoformat(),
                "category": "assignment",
                "source": "moodle",
            })

        if loaded:
            await session.commit()

    logger.info("Upserted %d new Moodle deadlines.", len(loaded))
    return loaded


# ─── Google Calendar Sync ─────────────────────────────────────────────────────


async def sync_deadlines_to_calendar() -> int:
    """Sync unlinked Deadline rows to Google Calendar.

    For each Deadline without a calendar_event_id, calls create_calendar_event()
    and stores the returned event ID back on the Deadline row.

    Returns:
        Number of deadlines synced to calendar.
    """
    from app.connectors.gmail.calendar_client import create_calendar_event

    synced = 0

    async with async_session_maker() as session:
        result = await session.exec(
            select(Deadline).where(
                Deadline.calendar_event_id == None,  # noqa: E711
                Deadline.status == "upcoming",
            )
        )
        deadlines = result.all()

        if not deadlines:
            logger.debug("No deadlines to sync to Google Calendar.")
            return 0

        for deadline in deadlines:
            try:
                date_str = deadline.due_datetime.strftime("%Y-%m-%d")
                time_str = deadline.due_datetime.strftime("%H:%M")

                result_event = create_calendar_event(
                    title=f"[{deadline.category.upper()}] {deadline.title}",
                    date=date_str,
                    time=time_str,
                    description=f"Source: {deadline.source}\nCategory: {deadline.category}",
                    duration_hours=1,
                )

                if "error" in result_event:
                    logger.warning(
                        "Calendar sync failed for deadline %d (%s): %s",
                        deadline.id,
                        deadline.title,
                        result_event["error"],
                    )
                    # Stop trying further if auth is the issue
                    if "Not authenticated" in str(result_event["error"]):
                        logger.info("Google Calendar not authenticated — skipping remaining.")
                        break
                    continue

                # Store the event ID
                deadline.calendar_event_id = result_event.get("event_id")
                session.add(deadline)
                synced += 1
                logger.info(
                    "Synced deadline %d to calendar: %s (event_id=%s)",
                    deadline.id,
                    deadline.title,
                    deadline.calendar_event_id,
                )

            except Exception as e:
                logger.warning("Calendar sync error for deadline %d: %s", deadline.id, e)
                continue

        if synced:
            await session.commit()

    logger.info("Synced %d deadlines to Google Calendar.", synced)
    return synced

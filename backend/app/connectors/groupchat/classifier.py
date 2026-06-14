"""Group chat message classifier.

Reuses the email_classifier.py category logic to classify group chat messages
into: DEADLINE, PLACEMENT, EXAM, FEE, EVENT, ANNOUNCEMENT, GENERAL.

STATUS: READY — logic is reusable, just needs real messages fed in.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Reuse keyword sets from email_classifier (imported at function level to avoid
# circular deps and keep this module testable standalone)

_DEADLINE_KEYWORDS = [
    "deadline", "due date", "submit by", "submission deadline",
    "last date", "before", "by end of", "upload by",
]

_PLACEMENT_KEYWORDS = [
    "campus drive", "placement drive", "shortlisted",
    "selection round", "online test", "aptitude test",
    "ppo", "pre-placement", "hiring",
]

_EXAM_KEYWORDS = [
    "cat-1", "cat-2", "cat 1", "cat 2", "fat exam",
    "end semester", "exam schedule", "hall ticket",
    "seating arrangement", "grade card",
]

_FEE_KEYWORDS = [
    "fee payment", "fee due", "pay before", "fee reminder",
    "hostel fee", "exam fee", "registration fee",
]


def classify_group_message(text: str, group_name: str = "") -> dict:
    """Classify a group chat message into category + priority.

    Args:
        text: Normalized message text.
        group_name: Source group name (may influence classification).

    Returns:
        Dict with: category, priority, is_actionable
    """
    if not text or len(text.strip()) < 10:
        return {"category": "GENERAL", "priority": "low", "is_actionable": False}

    lower = text.lower()

    # Check categories in order of specificity
    if any(kw in lower for kw in _PLACEMENT_KEYWORDS):
        return {"category": "PLACEMENT", "priority": "high", "is_actionable": True}

    if any(kw in lower for kw in _FEE_KEYWORDS):
        return {"category": "FEE", "priority": "high", "is_actionable": True}

    if any(kw in lower for kw in _EXAM_KEYWORDS):
        return {"category": "EXAM", "priority": "high", "is_actionable": True}

    if any(kw in lower for kw in _DEADLINE_KEYWORDS):
        return {"category": "DEADLINE", "priority": "normal", "is_actionable": True}

    # Check for date patterns (suggests deadline/event)
    date_pattern = re.search(
        r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))",
        lower,
    )
    if date_pattern:
        return {"category": "ANNOUNCEMENT", "priority": "normal", "is_actionable": True}

    return {"category": "GENERAL", "priority": "low", "is_actionable": False}

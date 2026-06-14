"""Rule-based email classifier for CampusFlow.

Classifies college emails using keyword matching — no API needed, works offline.
"""


def classify_email(subject: str, sender: str, body: str) -> dict:
    """Classify a single email by keyword matching."""
    text = (subject + " " + body).lower()
    sender_lower = sender.lower()

    # PLACEMENT FIRST — highest priority check (CDC emails often contain "result"/"test")
    if any(w in text for w in ["placement", "recruit", "cdc", "internship", "intern", "hiring", "campus drive", "ppo", "fte", "job offer", "selection", "shortlist", "aptitude", "drive"]) or "cdc" in sender_lower or "placement" in sender_lower:
        category, priority = "PLACEMENT", "high"
    elif any(w in text for w in ["result", "grade", "marks", "score", "gpa", "cgpa", "pass", "fail", "exam", "test", "quiz", "internal", "fat", "cat"]):
        category, priority = "EXAM", "high"
    elif any(w in text for w in ["fee", "payment", "due", "hostel", "fine", "challan"]):
        category, priority = "FEE", "high"
    elif any(w in text for w in ["event", "fest", "workshop", "seminar", "webinar", "hackathon", "symposium"]):
        category, priority = "EVENT", "medium"
    elif any(w in text for w in ["announcement", "notice", "circular", "important", "attention", "reminder"]):
        category, priority = "ANNOUNCEMENT", "medium"
    else:
        category, priority = "GENERAL", "low"

    summary = subject[:100] if subject else "No subject"
    return {"category": category, "priority": priority, "summary": summary}


def classify_emails(emails: list[dict]) -> list[dict]:
    """Classify a batch of emails."""
    return [
        classify_email(
            e.get("subject", ""),
            e.get("sender", ""),
            e.get("body_text", ""),
        )
        for e in emails
    ]

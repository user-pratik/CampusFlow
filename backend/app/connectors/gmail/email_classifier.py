"""Rule-based email classifier for CampusFlow.

Classifies college emails using keyword matching with urgency-aware priority logic.
Priority is based on actionability + deadline proximity, not category alone.

Key design principles:
- Noise/promotional senders are caught FIRST and get low priority
- Category is determined by context, not isolated keyword matches
- PLACEMENT = actual job/internship postings from CDC/placement cell
- "high" priority requires genuine urgency (deadline + actionability)
- Generic forwards, newsletters, and promotional mail stay at "low"
"""

import re

# ---------------------------------------------------------------------------
# NOISE FILTERS — these senders/subjects are ALWAYS low-priority regardless
# of what keywords appear in the body. Checked first.
# ---------------------------------------------------------------------------

_NOISE_SENDERS = [
    "unstop",
    "dare2compete",
    "kaggle",
    "read.ai",
    "readai",
    "noreply@google",
    "no-reply@accounts.google",
    "security-noreply",
    "newsletter",
    "digest",
    "mailer-daemon",
    "coursera",
    "udemy",
    "linkedin",
    "internshala",
    "prosple",
    "edutantr",
    "naukri",
    "indeed",
    "glassdoor",
    "hackerrank",
    "hackerearth",
    "leetcode",
    "geeksforgeeks",
    "simplilearn",
    "unacademy",
    "byjus",
    "skillshare",
    "n8n.io",
    "notion.so",
    "slack",
    "trello",
    "canva",
]

_NOISE_SUBJECT_PATTERNS = [
    r"security alert",
    r"welcome to",
    r"getting started",
    r"weekly digest",
    r"monthly digest",
    r"newsletter",
    r"new competition",
    r"competition launch",
    r"verify your email",
    r"confirm your email",
    r"reset.*password",
    r"blood donor",
    r"student council.*position",
    r"(earn|win).*stipend",
    r"level up your skills",
    r"ready to.*\?",
    r"recommendations? from",
    r"build your career",
    r"few hours left",
    r"learn from.*through",
    r"new graduate job",
]

# Subject patterns that indicate this is NOT a real placement/job email
# even if the sender contains "placement"
_NON_PLACEMENT_SUBJECT_PATTERNS = [
    r"student council",
    r"blood don",
    r"webinar",
    r"workshop",
    r"seminar",
    r"cultural",
    r"sports",
    r"nss",
    r"ncc",
    r"club.*registration",
    r"welfare",
]

# ---------------------------------------------------------------------------
# Urgency signals — pushes priority toward "high" when combined with actionable
# ---------------------------------------------------------------------------
_URGENCY_KEYWORDS = [
    "last date",
    "deadline",
    "mandatory",
    "compulsory",
    "blacklist",
    "debarred",
    "failing",
    "immediately",
    "within 24 hour",
    "within 48 hour",
    "by tomorrow",
    "today only",
    "urgent",
    "action required",
    "do not miss",
    "final reminder",
]

_DEADLINE_PATTERN = re.compile(
    r"(last date|deadline|due|register before|apply by|submit by|report by|expires?|scheduled on|scheduled for)"
    r"\s*[:\-]?\s*"
    r"(\d{1,2}(?:st|nd|rd|th)?\s*[\s/\-]\s*(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|\d{1,2})\s*[\s/\-]\s*\d{2,4}"
    r"|\d{1,2}\s*(?:days?|hours?))",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Category keyword sets — used for classification AFTER noise filtering
# ---------------------------------------------------------------------------

# PLACEMENT: Only real CDC/placement postings. Not promotional job boards.
_PLACEMENT_KEYWORDS_STRONG = [
    "campus drive",
    "ppo",
    "fte ",
    "pre-placement",
    "placement drive",
    "shortlisted for",
    "selection round",
    "online test is scheduled",
    "aptitude test scheduled",
    "report to placement",
]

# These only count if sender is from placement cell
_PLACEMENT_KEYWORDS_SENDER_DEPENDENT = [
    "hiring",
    "recruit",
    "applied students",
    "kind attention",
    "attention students",
    "report to",
]

_PLACEMENT_SENDER_PATTERNS = ["placement", "cdc", "career"]

_EXAM_KEYWORDS = [
    "grade card",
    "marks published",
    "exam schedule",
    "hall ticket",
    "seating arrangement",
    "revaluation result",
    "internal assessment",
    "fat exam",
    "cat-1 exam",
    "cat-2 exam",
    "cat 1 exam",
    "cat 2 exam",
    "end semester",
]

_FEE_KEYWORDS = [
    "fee payment",
    "fee due",
    "hostel fee",
    "tuition fee",
    "fine amount",
    "challan",
    "pay before",
    "fee reminder",
]

_EVENT_KEYWORDS = [
    "fest",
    "workshop",
    "seminar",
    "webinar",
    "hackathon",
    "symposium",
    "cultural event",
    "tech talk",
    "guest lecture",
    "inauguration",
    "blood don",  # blood donation drives are events
]

_ANNOUNCEMENT_KEYWORDS = [
    "circular",
    "notice",
    "official announcement",
    "important update",
    "student council",
    "election",
    "nomination",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _is_noise_sender(sender: str) -> bool:
    """Check if sender matches known bulk/marketing/promotional senders."""
    s = sender.lower()
    return any(ns in s for ns in _NOISE_SENDERS)


def _is_noise_subject(subject: str) -> bool:
    """Check if subject matches known low-relevance patterns."""
    s = subject.lower()
    return any(re.search(pat, s) for pat in _NOISE_SUBJECT_PATTERNS)


def _is_non_placement_subject(subject: str) -> bool:
    """Check if subject indicates this is NOT a placement email despite sender."""
    s = subject.lower()
    return any(re.search(pat, s) for pat in _NON_PLACEMENT_SUBJECT_PATTERNS)


def _is_placement_sender(sender: str) -> bool:
    """Check if sender is an authoritative placement/CDC source."""
    s = sender.lower()
    return any(kw in s for kw in _PLACEMENT_SENDER_PATTERNS)


def _has_urgency_signal(text: str) -> bool:
    """Check if text contains urgency indicators."""
    return any(kw in text for kw in _URGENCY_KEYWORDS)


def _has_near_deadline(text: str) -> bool:
    """Check if text mentions a deadline."""
    return bool(_DEADLINE_PATTERN.search(text))


def _is_actionable_email(text: str, category: str) -> bool:
    """Determine if an email requires the student to take action.

    Actionable = requires response/registration/submission within a timeframe.
    Non-actionable = FYI, digest, newsletter, informational announcement.
    """
    actionable_signals = [
        "register before",
        "apply by",
        "submit by",
        "fill the form",
        "fill form",
        "upload before",
        "attend mandatory",
        "report to",
        "last date to",
        "shortlisted",
        "selected for",
        "appear for",
        "slot booking",
        "is scheduled on",
        "scheduled for",
        "kind attention",
        "attention students",
        "check the portal",
        "check portal",
    ]
    non_actionable_signals = [
        "digest",
        "newsletter",
        "weekly update",
        "monthly update",
        "recommendations for you",
        "you might like",
        "trending",
        "new on",
        "tips for",
        "getting started",
        "welcome",
        "learn from",
        "build your career",
        "level up",
    ]

    if any(sig in text for sig in non_actionable_signals):
        return False
    if any(sig in text for sig in actionable_signals):
        return True
    return False


def _compute_priority(category: str, text: str, is_actionable: bool) -> str:
    """Determine priority based on actionability + urgency, not category alone.

    Rules:
    - "high" ONLY if: actionable AND (has urgency signal OR near deadline)
    - "medium" if: actionable but no immediate urgency
    - "low" otherwise (informational, no action needed)
    """
    has_urgency = _has_urgency_signal(text)
    has_deadline = _has_near_deadline(text)

    if category == "FEE" and (has_deadline or has_urgency):
        return "high"

    if is_actionable and (has_urgency or has_deadline):
        return "high"

    if is_actionable:
        return "medium"

    # Non-actionable: always low or medium based on category importance
    if category in ("FEE",):
        return "medium"

    return "low"


# ---------------------------------------------------------------------------
# Main classification function
# ---------------------------------------------------------------------------

def classify_email(subject: str, sender: str, body: str) -> dict:
    """Classify a single email with tight keyword matching and urgency-aware priority.

    Returns: {"category", "priority", "summary", "actionable"}
    """
    text = f"{subject} {body}".lower()
    sender_lower = sender.lower()

    # --- STEP 1: Noise filter (promotional / third-party / irrelevant) ---
    if _is_noise_sender(sender) or _is_noise_subject(subject):
        category = _categorize_noise(text)
        return {
            "category": category,
            "priority": "low",
            "summary": subject[:100] if subject else "No subject",
            "actionable": False,
        }

    # --- STEP 2: Check if sender is placement cell BUT subject is non-placement ---
    is_placement_src = _is_placement_sender(sender)
    is_non_placement = _is_non_placement_subject(subject)

    if is_placement_src and is_non_placement:
        # Forwarded through placement group but not actually a job
        category = _categorize_non_placement(text)
        actionable = _is_actionable_email(text, category)
        priority = _compute_priority(category, text, actionable)
        return {
            "category": category,
            "priority": priority,
            "summary": subject[:100] if subject else "No subject",
            "actionable": actionable,
        }

    # --- STEP 3: Real placement classification ---
    if is_placement_src:
        # Sender is CDC/placement — check if it's actually a job/test posting
        if any(kw in text for kw in _PLACEMENT_KEYWORDS_STRONG + _PLACEMENT_KEYWORDS_SENDER_DEPENDENT):
            actionable = _is_actionable_email(text, "PLACEMENT")
            priority = _compute_priority("PLACEMENT", text, actionable)
            return {
                "category": "PLACEMENT",
                "priority": priority,
                "summary": subject[:100] if subject else "No subject",
                "actionable": actionable,
            }
        # Placement sender but generic content — still PLACEMENT but lower priority
        return {
            "category": "PLACEMENT",
            "priority": "medium",
            "summary": subject[:100] if subject else "No subject",
            "actionable": False,
        }

    # Strong placement keywords from non-placement sender (rare but valid)
    if any(kw in text for kw in _PLACEMENT_KEYWORDS_STRONG):
        actionable = _is_actionable_email(text, "PLACEMENT")
        priority = _compute_priority("PLACEMENT", text, actionable)
        return {
            "category": "PLACEMENT",
            "priority": priority,
            "summary": subject[:100] if subject else "No subject",
            "actionable": actionable,
        }

    # --- STEP 4: Other categories (order: FEE > EXAM > EVENT > ANNOUNCEMENT > GENERAL) ---
    # FEE first (financial urgency)
    if any(kw in text for kw in _FEE_KEYWORDS):
        actionable = _is_actionable_email(text, "FEE")
        priority = _compute_priority("FEE", text, actionable)
        return {
            "category": "FEE",
            "priority": priority,
            "summary": subject[:100] if subject else "No subject",
            "actionable": actionable,
        }

    # EXAM
    if any(kw in text for kw in _EXAM_KEYWORDS):
        actionable = _is_actionable_email(text, "EXAM")
        priority = _compute_priority("EXAM", text, actionable)
        return {
            "category": "EXAM",
            "priority": priority,
            "summary": subject[:100] if subject else "No subject",
            "actionable": actionable,
        }

    # EVENT
    if any(kw in text for kw in _EVENT_KEYWORDS):
        actionable = _is_actionable_email(text, "EVENT")
        priority = _compute_priority("EVENT", text, actionable)
        return {
            "category": "EVENT",
            "priority": priority,
            "summary": subject[:100] if subject else "No subject",
            "actionable": actionable,
        }

    # ANNOUNCEMENT
    if any(kw in text for kw in _ANNOUNCEMENT_KEYWORDS):
        actionable = _is_actionable_email(text, "ANNOUNCEMENT")
        priority = _compute_priority("ANNOUNCEMENT", text, actionable)
        return {
            "category": "ANNOUNCEMENT",
            "priority": priority,
            "summary": subject[:100] if subject else "No subject",
            "actionable": actionable,
        }

    # GENERAL — nothing matched
    return {
        "category": "GENERAL",
        "priority": "low",
        "summary": subject[:100] if subject else "No subject",
        "actionable": False,
    }


def _categorize_noise(text: str) -> str:
    """Assign a soft category to noise emails (for display only, always low priority)."""
    if any(kw in text for kw in _EVENT_KEYWORDS):
        return "EVENT"
    if any(kw in text for kw in _ANNOUNCEMENT_KEYWORDS):
        return "ANNOUNCEMENT"
    return "GENERAL"


def _categorize_non_placement(text: str) -> str:
    """Categorize emails forwarded via placement group that aren't actually jobs."""
    if any(kw in text for kw in _EVENT_KEYWORDS):
        return "EVENT"
    if any(kw in text for kw in _ANNOUNCEMENT_KEYWORDS):
        return "ANNOUNCEMENT"
    if any(kw in text for kw in _EXAM_KEYWORDS):
        return "EXAM"
    return "GENERAL"


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

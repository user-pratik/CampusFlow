"""Placement Prep Agent — extracts placement drives from Gmail and generates prep checklists.

Scans EmailNotification where category=PLACEMENT, uses Groq LLM to extract:
- Company name, drive date, round types, role, package, eligibility
Creates PlacementDrive + default PrepChecklist items per round type.
Deduplicates on source_email_id (gmail_msg_id).
"""

import json
import logging
from datetime import datetime

from sqlmodel import select

from app.database import async_session_maker
from app.models import EmailNotification, PlacementDrive, PrepChecklist
from app.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

# Default prep checklist items per round type
DEFAULT_PREP_ITEMS: dict[str, list[str]] = {
    "aptitude": [
        "Practice quantitative aptitude (30 problems)",
        "Review logical reasoning patterns",
        "Time management: attempt mock test under 30min",
    ],
    "coding": [
        "Solve 5 medium LeetCode problems",
        "Review DSA: arrays, trees, graphs, DP",
        "Practice timed coding contest (90min)",
        "Review company-specific past questions",
    ],
    "technical": [
        "Revise core CS subjects (OS, DBMS, CN, OOP)",
        "Prepare 2-3 project explanations",
        "Review system design basics",
    ],
    "interview": [
        "Prepare self-introduction (60 seconds)",
        "Research company: products, culture, recent news",
        "Prepare 3 behavioral stories (STAR format)",
        "Review resume — be ready to explain every line",
    ],
    "hr": [
        "Prepare answers: strengths, weaknesses, why this company",
        "Research company values and culture",
        "Prepare questions to ask the interviewer",
    ],
    "group_discussion": [
        "Read current affairs (last 2 weeks)",
        "Practice structuring arguments in 2 minutes",
        "Review common GD topics for tech companies",
    ],
}


async def extract_placement_drives() -> list[dict]:
    """Scan placement emails and extract drive details via Groq LLM.

    Returns:
        List of dicts summarizing newly extracted drives.
    """
    extracted: list[dict] = []

    async with async_session_maker() as session:
        # Get placement-category emails
        result = await session.exec(
            select(EmailNotification).where(EmailNotification.category == "PLACEMENT")
        )
        emails = result.all()

        if not emails:
            logger.info("No placement emails found.")
            return extracted

        # Check which gmail_msg_ids are already processed
        existing_result = await session.exec(
            select(PlacementDrive.source_email_id)
        )
        existing_ids = set(existing_result.all())

        new_emails = [e for e in emails if e.gmail_msg_id not in existing_ids]

        if not new_emails:
            logger.info("All %d placement emails already processed.", len(emails))
            return extracted

        logger.info("Processing %d new placement emails.", len(new_emails))

        # Process in batches of 5
        for batch_start in range(0, len(new_emails), 5):
            batch = new_emails[batch_start:batch_start + 5]
            batch_results = await _extract_drives_batch(batch)

            for drive_info in batch_results:
                # Create PlacementDrive
                drive = PlacementDrive(
                    company_name=drive_info["company_name"],
                    drive_date=drive_info.get("drive_date"),
                    rounds=json.dumps(drive_info.get("rounds", [])),
                    status="upcoming",
                    applied=False,
                    source_email_id=drive_info["source_email_id"],
                    role=drive_info.get("role"),
                    package=drive_info.get("package"),
                    eligibility=drive_info.get("eligibility"),
                    eligible_degree=drive_info.get("eligible_degree"),
                    eligible_batch=drive_info.get("eligible_batch"),
                    min_cgpa=drive_info.get("min_cgpa"),
                )
                session.add(drive)
                await session.flush()  # Get the ID

                # Create PrepChecklist with default items based on round types
                checklist_items = _generate_checklist(drive_info.get("rounds", []))
                checklist = PrepChecklist(
                    drive_id=drive.id,
                    items=json.dumps(checklist_items),
                )
                session.add(checklist)

                extracted.append({
                    "company": drive_info["company_name"],
                    "role": drive_info.get("role"),
                    "drive_date": drive_info["drive_date"].isoformat() if drive_info.get("drive_date") else None,
                    "rounds": drive_info.get("rounds", []),
                    "checklist_items": len(checklist_items),
                })

        await session.commit()

    logger.info("Extracted %d placement drives.", len(extracted))
    return extracted


async def _extract_drives_batch(emails: list[EmailNotification]) -> list[dict]:
    """Use Groq LLM to extract placement drive info from a batch of emails.

    Returns:
        List of dicts with: company_name, drive_date, rounds, role, package,
        eligibility, source_email_id
    """
    email_texts = []
    for i, email in enumerate(emails):
        text = (
            f"[Email {i+1}] (msg_id: {email.gmail_msg_id})\n"
            f"Subject: {email.subject or 'N/A'}\n"
            f"From: {email.sender or 'N/A'}\n"
            f"Date: {email.received_at.isoformat() if email.received_at else 'N/A'}\n"
            f"Summary: {email.summary or ''}\n"
            f"Body: {(email.raw_body or '')[:800]}\n"
        )
        email_texts.append(text)

    prompt = f"""Extract placement drive information from these college emails. For each email about a campus placement drive, output a JSON array of objects.

Each object should have:
- "msg_id": the msg_id from the email header
- "company_name": company name (e.g. "Amazon", "Microsoft")
- "role": job role or position (e.g. "SDE Intern", "Full Stack Developer"), null if not specified
- "drive_date": ISO datetime (YYYY-MM-DDTHH:MM:SS) of the test/drive date, null if not clear
- "rounds": array of round types from: ["aptitude", "coding", "technical", "interview", "hr", "group_discussion"]
- "package": CTC or stipend info as string (e.g. "12 LPA", "50K/month"), null if not specified
- "eligibility": raw eligibility criteria text (e.g. "CSE/IT branches, 2027 batch, CGPA > 7.0"), null if not specified
- "eligible_degree": degree/branch required (e.g. "BTech CSE/IT/ECE"), null if not mentioned
- "eligible_batch": batch year(s) required (e.g. "2027" or "2026/2027"), null if not mentioned
- "min_cgpa": minimum CGPA as a number (e.g. 7.0), null if not mentioned

If an email is not about a specific placement drive (e.g. just a newsletter), skip it.
Today's date: {datetime.now().strftime("%Y-%m-%d")}

EMAILS:
{"".join(email_texts)}

Respond ONLY with a JSON array. If no drives found, respond with [].
"""

    try:
        response = await chat_completion(
            messages=[
                {"role": "system", "content": "You extract placement drive details from college emails. Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )

        data = json.loads(response)
        if isinstance(data, dict):
            items = data.get("drives", data.get("results", data.get("placements", [])))
        elif isinstance(data, list):
            items = data
        else:
            items = []

        results = []
        for item in items:
            company = item.get("company_name", "").strip()
            if not company:
                continue

            # Parse drive date
            drive_date = None
            date_str = item.get("drive_date")
            if date_str:
                try:
                    drive_date = datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    pass

            # Normalize rounds
            valid_rounds = {"aptitude", "coding", "technical", "interview", "hr", "group_discussion"}
            rounds = [r.lower().strip() for r in item.get("rounds", []) if r.lower().strip() in valid_rounds]
            if not rounds:
                # Default assumption for tech companies
                rounds = ["coding", "technical", "interview"]

            results.append({
                "company_name": company,
                "drive_date": drive_date,
                "rounds": rounds,
                "role": item.get("role"),
                "package": item.get("package"),
                "eligibility": item.get("eligibility"),
                "eligible_degree": item.get("eligible_degree"),
                "eligible_batch": item.get("eligible_batch"),
                "min_cgpa": _parse_cgpa(item.get("min_cgpa")),
                "source_email_id": item.get("msg_id", ""),
            })

        return results

    except Exception as e:
        logger.warning("LLM extraction failed for placement batch: %s", e)
        return []


def _generate_checklist(rounds: list[str]) -> list[dict]:
    """Generate default prep checklist items based on round types.

    Returns:
        List of dicts: {task, completed, round_type}
    """
    items: list[dict] = []

    for round_type in rounds:
        tasks = DEFAULT_PREP_ITEMS.get(round_type, [])
        for task in tasks:
            items.append({
                "task": task,
                "completed": False,
                "round_type": round_type,
            })

    # Always add general items
    general = [
        {"task": "Update resume with latest projects", "completed": False, "round_type": "general"},
        {"task": "Test internet connection and setup", "completed": False, "round_type": "general"},
    ]
    items.extend(general)

    return items


# ─── Eligibility Checking ─────────────────────────────────────────────────────

# Hardcoded student profile constants
STUDENT_PROFILE = {
    "degree": "BTech",
    "branch": "CSE AIML",
    "batch": "2027",
    "cgpa": 9.11,
}

# Branch aliases that would match CSE AIML
CSE_BRANCH_ALIASES = {
    "cse", "cs", "it", "cse aiml", "cse ai", "aiml", "ai/ml",
    "computer science", "information technology", "all branches",
}


def check_eligibility(drive: PlacementDrive) -> str:
    """Determine eligibility status against student profile.

    Returns:
        "Eligible", "Likely Not Eligible", or "Unclear"
    """
    reasons_ineligible: list[str] = []
    has_criteria = False

    # Check CGPA
    if drive.min_cgpa is not None:
        has_criteria = True
        if STUDENT_PROFILE["cgpa"] < drive.min_cgpa:
            reasons_ineligible.append("cgpa")

    # Check batch
    if drive.eligible_batch:
        has_criteria = True
        batch_str = drive.eligible_batch.lower().replace(" ", "")
        # Handle "2027", "2026/2027", "2026,2027" formats
        student_batch = STUDENT_PROFILE["batch"]
        if student_batch not in batch_str:
            reasons_ineligible.append("batch")

    # Check degree/branch
    if drive.eligible_degree:
        has_criteria = True
        degree_lower = drive.eligible_degree.lower()
        # Check if any CSE alias matches
        branch_match = any(alias in degree_lower for alias in CSE_BRANCH_ALIASES)
        if not branch_match:
            reasons_ineligible.append("branch")

    if not has_criteria:
        return "Unclear"

    if reasons_ineligible:
        return "Likely Not Eligible"

    return "Eligible"


def _parse_cgpa(value) -> float | None:
    """Safely parse a CGPA value from LLM output."""
    if value is None:
        return None
    try:
        cgpa = float(value)
        return cgpa if 0 <= cgpa <= 10 else None
    except (ValueError, TypeError):
        return None

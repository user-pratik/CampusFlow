"""Workflow Planner — LLM-driven combined routing + scoped data retrieval.

Replaces the two-step _classify_intent + _gather_context pattern with a single
LLM reasoning step that decides:
  (a) which agent/workflow applies
  (b) what specific data to retrieve (with filters)
  (c) forwards reasoning + prefetched data to the leaf agent

Feature-flagged via USE_WORKFLOW_PLANNER env var (default: true).
Falls back to legacy rule-based routing when disabled.
"""

import json
import logging
import os
from datetime import datetime, timedelta

from app.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

USE_WORKFLOW_PLANNER = os.getenv("USE_WORKFLOW_PLANNER", "true").lower() == "true"


# ─── Planner System Prompt ────────────────────────────────────────────────────

PLANNER_SYSTEM_PROMPT = """\
You are the workflow planner for CampusFlow, a college student assistant at VIT.
Given the user's message, decide which agent should handle it and what data to retrieve.

AVAILABLE AGENTS:
1. "attendance_risk" — Attendance tracking: per-course %, classes attended/missed, skip risk.
   Data source: attendance table (fields: course_code, course_title, percentage, attended, total)
2. "gpa_projection" — CGPA/GPA: grade projection, what-if analysis, target CGPA planning.
   Data source: course_marks (course_code, course_title, mark_title, score), academic_profile (cgpa, total_credits)
3. "deadlines" — Upcoming deadlines from Gmail/manual/Moodle.
   Data source: deadlines (title, due_datetime, category, source, status)
4. "placements" — Placement drives, eligibility, prep checklists.
   Data source: placement_drives (company_name, drive_date, rounds, eligibility_status, applied)
5. "timetable" — Today's class schedule and free slots.
   Data source: timetable_slots (day_of_week, start_time, end_time, course_code, venue, slot_type)
6. "regulations" — VIT academic policies (attendance rules, grading, FFCS, exams, credits).
   Data source: academic_regulations.json (no DB query needed)
7. "chat" — General conversation, vague queries, multi-topic summaries, things that don't fit one agent.
   No specific data source — orchestrator answers conversationally.

DECISION RULES:
- "attendance" + skip/bunk/classes/percentage context → attendance_risk
- "CGPA"/"GPA"/"grade"/"marks"/"what if grade" → gpa_projection
- "deadline"/"due"/"submission" (no company name) → deadlines
- "placement"/"drive"/"company"/"hiring" → placements
- "timetable"/"schedule"/"today's class"/"free slot" → timetable
- Policy questions ("do I need", "what's the rule", "requirement", "allowed") → regulations
- Vague/greeting/multi-domain/ambiguous → chat
- If genuinely unsure between two agents → chat (never guess)

DATA FILTERS (use to scope retrieval — don't always fetch everything):
- course_code: specific course code if mentioned (e.g. "BCSE305L")
- category: filter by category if mentioned (e.g. "exam", "fee", "placement")
- date_range: "today", "this_week", "next_week", "this_month", or null
- status: "upcoming", "completed", etc.
- target_cgpa: float if user mentions a target

IMPORTANT NEGATIVE EXAMPLES:
- "how much more attendance do I need to get over 50%" → attendance_risk (NOT gpa), filters: null (all courses)
- "do I need 75%" → regulations (policy question, NOT attendance calculator)
- "what's my BCSE305L attendance" → attendance_risk, filters: {course_code: "BCSE305L"}
- "what's due this week from placements" → deadlines, filters: {date_range: "this_week", category: "placement"}
- "how am I doing" → chat (too vague for any specific agent)
- "if I get an A in probability" → gpa_projection, filters: {course_code: "BMAT301L"} (infer code if possible)

STUDENT PROFILE (always available for reasoning):
- Name: Pratik Anand, Reg: 23BRS1143, BTech CSE AI&ML, Year 3, CGPA: 9.11, No backlogs.
- The 9-pointer exemption (CGPA >= 9.0, no backlogs) APPLIES to this student.
- When answering regulations questions about attendance, state definitively whether this student is exempt — don't hedge with "might be" or "you should check".

Return ONLY a JSON object:
{
  "action": "spawn_window" | "chat_only" | "spawn_and_answer",
  "agent": "<agent name from list above>",
  "data_request": {
    "source": "<attendance | course_marks | deadlines | placements | timetable | regulations | null>",
    "filters": {
      "course_code": "<string or null>",
      "category": "<string or null>",
      "date_range": "<today | this_week | next_week | this_month | null>",
      "status": "<string or null>",
      "target_cgpa": "<float or null>"
    }
  },
  "reasoning": "<1-2 sentence explanation of why this agent and these filters>",
  "confidence": <0.0 to 1.0>
}

RULES:
- action="spawn_window": user wants to SEE structured data (attendance table, deadline list, etc.)
- action="chat_only": user wants a conversational answer (policy question, vague, multi-turn)
- action="spawn_and_answer": user wants both structured data AND a text explanation
- If confidence < 0.7, set agent to "chat" regardless of what you think
- For policy/regulation questions, use action="chat_only" with agent="regulations"
- filters can be partially filled — null means "don't filter on this dimension"
"""


# ─── Data Models ──────────────────────────────────────────────────────────────


class WorkflowPlan:
    """Result of the planner's reasoning step."""

    def __init__(self, raw: dict):
        self.action: str = raw.get("action", "chat_only")
        self.agent: str = raw.get("agent", "chat")
        self.data_request: dict = raw.get("data_request", {})
        self.reasoning: str = raw.get("reasoning", "")
        self.confidence: float = raw.get("confidence", 0.5)
        self.source: str = self.data_request.get("source") or ""
        self.filters: dict = self.data_request.get("filters") or {}

    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.7

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "agent": self.agent,
            "data_request": self.data_request,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


# ─── Planner ──────────────────────────────────────────────────────────────────


async def plan_workflow(message: str, history: list[dict]) -> WorkflowPlan:
    """Single LLM call that decides agent + data scope + action.

    Args:
        message: User's current message.
        history: Recent conversation history.

    Returns:
        WorkflowPlan with routing decision and data retrieval spec.
    """
    history_text = ""
    if history:
        recent = history[-6:]
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:200]}" for m in recent
        )

    user_prompt = f"CONVERSATION HISTORY:\n{history_text}\n\nCURRENT MESSAGE: {message}"

    try:
        content = await chat_completion(
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=400,
            fast=True,
        )
        raw = json.loads(content)
        plan = WorkflowPlan(raw)

        # Enforce confidence threshold
        if not plan.is_confident and plan.agent != "chat":
            logger.info(
                "Planner low confidence %.2f for '%s' — falling back to chat.",
                plan.confidence, plan.agent,
            )
            plan.agent = "chat"
            plan.action = "chat_only"

        logger.info(
            "Workflow plan: agent=%s, action=%s, source=%s, filters=%s, confidence=%.2f | %s",
            plan.agent, plan.action, plan.source,
            json.dumps(plan.filters), plan.confidence, plan.reasoning,
        )
        return plan

    except Exception as e:
        logger.warning("Workflow planner failed: %s — using keyword fallback.", e)
        return _keyword_fallback(message)


def _keyword_fallback(message: str) -> WorkflowPlan:
    """Fast keyword-based fallback when the LLM planner is unavailable.

    This is NOT the primary classification — it only runs when the Groq API
    is down/rate-limited. It provides basic routing so the system doesn't
    collapse entirely to the generic greeting.
    """
    lower = message.lower()

    if any(w in lower for w in ["attendance", "attendence", "bunk", "absent", "classes attended"]):
        return WorkflowPlan({
            "action": "spawn_and_answer",
            "agent": "attendance_risk",
            "data_request": {"source": "attendance", "filters": {}},
            "reasoning": "Keyword fallback: attendance-related query (LLM unavailable)",
            "confidence": 0.8,
        })

    if any(w in lower for w in ["cgpa", "sgpa", "gpa", "grade point", "marks"]):
        return WorkflowPlan({
            "action": "spawn_and_answer",
            "agent": "gpa_projection",
            "data_request": {"source": "course_marks", "filters": {}},
            "reasoning": "Keyword fallback: GPA/marks query (LLM unavailable)",
            "confidence": 0.8,
        })

    if any(w in lower for w in ["timetable", "schedule", "free slot", "today's class"]):
        return WorkflowPlan({
            "action": "spawn_window",
            "agent": "timetable",
            "data_request": {"source": "timetable", "filters": {}},
            "reasoning": "Keyword fallback: timetable query (LLM unavailable)",
            "confidence": 0.8,
        })

    if any(w in lower for w in ["deadline", "due", "submission", "assignment"]):
        return WorkflowPlan({
            "action": "spawn_window",
            "agent": "deadlines",
            "data_request": {"source": "deadlines", "filters": {}},
            "reasoning": "Keyword fallback: deadline query (LLM unavailable)",
            "confidence": 0.8,
        })

    if any(w in lower for w in ["placement", "drive", "company", "recruit", "hiring"]):
        return WorkflowPlan({
            "action": "spawn_window",
            "agent": "placements",
            "data_request": {"source": "placements", "filters": {}},
            "reasoning": "Keyword fallback: placement query (LLM unavailable)",
            "confidence": 0.8,
        })

    if any(w in lower for w in ["rule", "regulation", "policy", "do i need", "required"]):
        return WorkflowPlan({
            "action": "chat_only",
            "agent": "regulations",
            "data_request": {"source": "regulations", "filters": {}},
            "reasoning": "Keyword fallback: regulations query (LLM unavailable)",
            "confidence": 0.8,
        })

    return WorkflowPlan({
        "action": "chat_only",
        "agent": "chat",
        "data_request": {},
        "reasoning": "Keyword fallback: no clear intent match (LLM unavailable)",
        "confidence": 0.5,
    })


# ─── Scoped Data Retrieval ────────────────────────────────────────────────────


async def retrieve_scoped_data(plan: WorkflowPlan) -> dict:
    """Retrieve data from DB using the planner's filters.

    Returns a dict of prefetched data matching the plan's data_request.
    If filters are empty/null, falls back to fetching everything for that source.
    """
    from app.database import async_session_maker
    from sqlmodel import select
    from app.models import Attendance, CourseMark, AcademicProfile, Deadline, PlacementDrive, TimetableSlot

    source = plan.source
    filters = plan.filters
    data: dict = {"source": source, "filters": filters}

    if not source or source == "null":
        return data

    async with async_session_maker() as session:
        if source == "attendance":
            query = select(Attendance).order_by(Attendance.course_code)
            if filters.get("course_code"):
                query = query.where(Attendance.course_code == filters["course_code"])
            result = await session.exec(query)
            rows = result.all()
            data["attendance"] = [
                {
                    "course_code": a.course_code,
                    "course_title": a.course_title,
                    "percentage": a.percentage,
                    "attended": a.attended,
                    "total": a.total,
                }
                for a in rows
            ]

        elif source == "course_marks":
            query = select(CourseMark).order_by(CourseMark.course_code)
            if filters.get("course_code"):
                query = query.where(CourseMark.course_code == filters["course_code"])
            result = await session.exec(query)
            rows = result.all()
            data["marks"] = [
                {
                    "course_code": m.course_code,
                    "course_title": m.course_title,
                    "mark_title": m.mark_title,
                    "max_mark": m.max_mark,
                    "score": m.score,
                    "weightage_mark": m.weightage_mark,
                    "status": m.status,
                }
                for m in rows
            ]
            # Also fetch academic profile for GPA context
            profile_result = await session.exec(
                select(AcademicProfile).order_by(AcademicProfile.updated_at.desc()).limit(1)
            )
            profile = profile_result.first()
            if profile:
                data["academic_profile"] = {
                    "cgpa": profile.cgpa,
                    "total_credits": profile.total_credits,
                }
            else:
                # Fallback to static user profile if DB has no synced data
                from app.utils.user_context import get_user_profile
                static = get_user_profile()
                if static.get("cgpa"):
                    data["academic_profile"] = {
                        "cgpa": static["cgpa"],
                        "total_credits": None,
                        "source_note": "From static profile (VTOP not synced yet)",
                    }

        elif source == "deadlines":
            query = select(Deadline).order_by(Deadline.due_datetime)
            if filters.get("status"):
                query = query.where(Deadline.status == filters["status"])
            else:
                query = query.where(Deadline.status == "upcoming")
            if filters.get("category"):
                query = query.where(Deadline.category == filters["category"])
            if filters.get("date_range"):
                now = datetime.utcnow()
                range_map = {
                    "today": timedelta(days=1),
                    "this_week": timedelta(days=7),
                    "next_week": timedelta(days=14),
                    "this_month": timedelta(days=30),
                }
                end = now + range_map.get(filters["date_range"], timedelta(days=30))
                query = query.where(Deadline.due_datetime >= now).where(Deadline.due_datetime <= end)
            result = await session.exec(query)
            rows = result.all()
            data["deadlines"] = [
                {
                    "title": d.title,
                    "due_datetime": d.due_datetime.isoformat(),
                    "category": d.category,
                    "source": d.source,
                    "status": d.status,
                }
                for d in rows
            ]

        elif source == "placements":
            query = select(PlacementDrive).order_by(PlacementDrive.drive_date)
            if filters.get("status"):
                query = query.where(PlacementDrive.status == filters["status"])
            result = await session.exec(query)
            rows = result.all()
            data["placements"] = [
                {
                    "company_name": p.company_name,
                    "role": p.role,
                    "drive_date": p.drive_date.isoformat() if p.drive_date else None,
                    "status": p.status,
                    "applied": p.applied,
                    "package": p.package,
                }
                for p in rows
            ]

        elif source == "timetable":
            day_name = filters.get("day") or datetime.now().strftime("%A")
            query = select(TimetableSlot).where(
                TimetableSlot.day_of_week == day_name
            ).order_by(TimetableSlot.start_time)
            result = await session.exec(query)
            rows = result.all()
            data["timetable"] = [
                {
                    "course_code": s.course_code,
                    "course_name": s.course_name,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "venue": s.venue,
                    "slot_type": s.slot_type,
                }
                for s in rows
            ]

        elif source == "regulations":
            from pathlib import Path
            reg_file = Path(__file__).resolve().parent.parent.parent / "data" / "fabricated" / "academic_regulations.json"
            if reg_file.exists():
                with open(reg_file, "r", encoding="utf-8") as f:
                    data["regulations"] = json.load(f)

    # ─── Always include student profile for context-dependent answers ─────────
    # Agents answering about regulations, attendance, or GPA need to know the
    # student's CGPA/backlogs to determine exemption eligibility.
    if source in ("regulations", "attendance", "course_marks") and "academic_profile" not in data:
        from app.utils.user_context import get_user_profile
        profile = get_user_profile()
        data["student_profile"] = {
            "name": profile.get("name"),
            "cgpa": profile.get("cgpa"),
            "reg_no": profile.get("reg_no"),
            "branch": profile.get("branch"),
            "year": profile.get("year"),
            "has_backlogs": False,  # From user_profile.json — no backlogs indicated
        }

    return data


# ─── Two-Pass Retrieval with Condition Resolution ─────────────────────────────

CONDITION_DETECTION_PROMPT = """\
You are analyzing retrieved content to determine if it contains conditional statements
whose conditions cannot be evaluated with the data currently available.

CURRENTLY AVAILABLE DATA KEYS: {available_keys}

RETRIEVED CONTENT (summarized):
{content_summary}

Does this content contain any conditional/exemption/eligibility language (e.g. "unless",
"if CGPA >= X", "provided that", "exempt if", "eligible if", "subject to", "minimum")
whose condition depends on student-specific data NOT already present in the available data?

If YES, identify what additional data source(s) and field(s) are needed to resolve the condition.

Available additional sources:
- "student_profile": name, cgpa, branch, year, reg_no, has_backlogs, degree, specialization
- "attendance": per-course attendance percentage, attended, total
- "course_marks": per-course marks, scores
- "academic_profile": cgpa, total_credits (from DB, may differ from static profile)
- "deadlines": upcoming deadlines with status
- "placements": placement drives with eligibility

Return ONLY a JSON object with keys: needs_followup (bool), unresolved_conditions (array of strings), additional_sources (array of objects with source, filters, reason).

If no unresolved conditions exist, return needs_followup=false with empty arrays.
"""


async def detect_unresolved_conditions(retrieved_data: dict) -> dict:
    """Pass 2 detection: check if retrieved content has unresolved conditional logic.

    Runs a lightweight LLM call to identify conditions in the retrieved data
    that depend on student-specific data not yet fetched.

    Args:
        retrieved_data: The data from Pass 1 retrieval.

    Returns:
        Dict with needs_followup, unresolved_conditions, additional_sources.
    """
    # Build a summary of what's in the retrieved data
    available_keys = list(retrieved_data.keys())

    # Summarize content for the LLM (cap size)
    content_summary = json.dumps(retrieved_data, indent=1, default=str)[:2500]

    prompt = CONDITION_DETECTION_PROMPT.format(
        available_keys=json.dumps(available_keys),
        content_summary=content_summary,
    )

    try:
        response = await chat_completion(
            messages=[
                {"role": "system", "content": "You detect unresolved conditions in retrieved data. Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=300,
            fast=True,
        )
        result = json.loads(response)
        logger.debug(
            "Condition detection: needs_followup=%s, sources=%s",
            result.get("needs_followup"),
            [s.get("source") for s in result.get("additional_sources", [])],
        )
        return result

    except Exception as e:
        logger.warning("Condition detection failed: %s — skipping Pass 2.", e)
        return {"needs_followup": False, "unresolved_conditions": [], "additional_sources": []}


async def retrieve_additional_data(additional_sources: list[dict]) -> dict:
    """Pass 2 retrieval: fetch the additional data identified by condition detection.

    Bounded to one follow-up round — fetches all identified sources in parallel.

    Args:
        additional_sources: List of {source, filters, reason} from condition detection.

    Returns:
        Dict of additional data keyed by source name.
    """
    from app.database import async_session_maker
    from sqlmodel import select
    from app.models import Attendance, CourseMark, AcademicProfile, Deadline, PlacementDrive

    additional_data: dict = {}

    async with async_session_maker() as session:
        for spec in additional_sources:
            source = spec.get("source", "")
            filters = spec.get("filters") or {}

            if source == "student_profile":
                from app.utils.user_context import get_user_profile
                profile = get_user_profile()
                additional_data["student_profile"] = {
                    "name": profile.get("name"),
                    "cgpa": profile.get("cgpa"),
                    "reg_no": profile.get("reg_no"),
                    "branch": profile.get("branch"),
                    "specialization": profile.get("specialization"),
                    "degree": profile.get("degree"),
                    "year": profile.get("year"),
                    "has_backlogs": False,
                }

            elif source == "academic_profile":
                result = await session.exec(
                    select(AcademicProfile).order_by(AcademicProfile.updated_at.desc()).limit(1)
                )
                profile = result.first()
                if profile:
                    additional_data["academic_profile"] = {
                        "cgpa": profile.cgpa,
                        "total_credits": profile.total_credits,
                        "overall_attendance": profile.overall_attendance,
                    }

            elif source == "attendance":
                query = select(Attendance).order_by(Attendance.course_code)
                if filters.get("course_code"):
                    query = query.where(Attendance.course_code == filters["course_code"])
                result = await session.exec(query)
                rows = result.all()
                additional_data["attendance"] = [
                    {
                        "course_code": a.course_code,
                        "percentage": a.percentage,
                        "attended": a.attended,
                        "total": a.total,
                    }
                    for a in rows
                ]

            elif source == "course_marks":
                query = select(CourseMark).order_by(CourseMark.course_code)
                if filters.get("course_code"):
                    query = query.where(CourseMark.course_code == filters["course_code"])
                result = await session.exec(query)
                rows = result.all()
                additional_data["course_marks"] = [
                    {"course_code": m.course_code, "score": m.score, "mark_title": m.mark_title}
                    for m in rows
                ]

            elif source == "deadlines":
                query = select(Deadline).where(Deadline.status == "upcoming").order_by(Deadline.due_datetime)
                result = await session.exec(query)
                rows = result.all()
                additional_data["deadlines"] = [
                    {"title": d.title, "due_datetime": d.due_datetime.isoformat(), "category": d.category}
                    for d in rows
                ]

            elif source == "placements":
                query = select(PlacementDrive).order_by(PlacementDrive.drive_date)
                result = await session.exec(query)
                rows = result.all()
                additional_data["placements"] = [
                    {"company_name": p.company_name, "drive_date": p.drive_date.isoformat() if p.drive_date else None}
                    for p in rows
                ]

    logger.info("Pass 2 retrieved additional data: %s", list(additional_data.keys()))
    return additional_data


async def retrieve_with_condition_resolution(plan: WorkflowPlan) -> dict:
    """Full two-pass retrieval pipeline.

    Pass 1: Retrieve data based on the planner's data_request.
    Condition detection: Check if retrieved content has unresolved conditions.
    Pass 2 (if needed): Retrieve additional data to resolve conditions.

    Returns merged data from both passes.
    """
    # Pass 1: Standard scoped retrieval
    data = await retrieve_scoped_data(plan)

    # Skip condition detection for sources unlikely to have conditional language
    # (timetable is purely factual, attendance is data, chat has no data)
    skip_detection_sources = {"timetable", "attendance", "course_marks", "placements", "deadlines", "null", ""}
    if plan.source in skip_detection_sources or not plan.source:
        return data

    # Condition detection: does the retrieved content have unresolved IF/UNLESS clauses?
    detection = await detect_unresolved_conditions(data)

    if not detection.get("needs_followup"):
        logger.debug("No unresolved conditions detected — skipping Pass 2.")
        return data

    # Pass 2: Retrieve the additional data needed to resolve conditions
    additional_sources = detection.get("additional_sources", [])
    if not additional_sources:
        return data

    logger.info(
        "Condition resolution needed: %s. Performing Pass 2 retrieval.",
        detection.get("unresolved_conditions", []),
    )

    additional_data = await retrieve_additional_data(additional_sources)

    # Merge Pass 2 data into the main data dict
    data.update(additional_data)
    data["_condition_resolution"] = {
        "pass2_triggered": True,
        "unresolved_conditions": detection.get("unresolved_conditions", []),
        "additional_sources_fetched": [s.get("source") for s in additional_sources],
    }

    return data


# ─── Orchestrator Context (passed to leaf agents) ────────────────────────────


class OrchestratorContext:
    """Context object forwarded from the planner to leaf agents.

    Contains the full reasoning chain so the leaf agent doesn't re-derive context.
    """

    def __init__(self, user_query: str, plan: WorkflowPlan, prefetched_data: dict):
        self.user_query = user_query
        self.plan = plan
        self.prefetched_data = prefetched_data

    def to_dict(self) -> dict:
        return {
            "user_query": self.user_query,
            "reasoning": self.plan.reasoning,
            "agent": self.plan.agent,
            "action": self.plan.action,
            "data_request": self.plan.data_request,
            "prefetched_data": self.prefetched_data,
            "confidence": self.plan.confidence,
        }

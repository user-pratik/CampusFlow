"""Orchestrator Agent -- Routes user queries to specialist agents and maintains conversation memory.

This is the central brain of CampusFlow's agentic system. It:
1. Classifies user intent
2. Gathers relevant context from DB + user profile
3. Routes to specialist agents (academic, schedule, action)
4. Maintains conversation history for multi-turn reasoning
5. Returns structured responses with suggested actions
"""

import json
import logging
from datetime import datetime

from app.agents.base import BaseAgent
from app.agents.academic_agent import AcademicAgent
from app.agents.schedule_agent import ScheduleAgent
from app.agents.action_agent import ActionAgent
from app.agents.connector_agent import ConnectorAgent
from app.agents.memory import ConversationMemory
from app.utils.llm_client import chat_completion
from app.utils.user_context import get_user_profile

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """\
You are an intent classifier for a college student assistant called CampusFlow.

Given the user's message and conversation history, classify the intent into ONE of these categories:

- "academic": Questions about marks, grades, CGPA, SGPA, GPA projection, course performance, improvement tips, academic regulations, exam schedule, grading policy, credit requirements, FFCS rules, withdrawal, backlogs, "what if I get grade X", "target CGPA"
- "attendance_risk": Questions SPECIFICALLY about attendance percentage, classes attended/missed, skipping/bunking classes, "how many classes can I skip", "75% threshold", course-specific attendance counts. NOT about marks, grades, or CGPA.
- "schedule": Requests to CREATE study plans, daily schedules, task checklists, time management, revision plans
- "action": Requests to set alarms, send messages, open assignments, create reminders, or any actionable task
- "connector": Questions about WhatsApp messages, emails, inbox, calendar events, timetable (today's classes/free slots), deadlines, upcoming exams, study groups, class schedule, what's due
- "general": General conversation, greetings, vague questions ("how am I doing", "what's up"), or queries that don't clearly fit ONE specific category

DISAMBIGUATION RULES (follow strictly):
1. "attendance" + "%"/"percent"/"skip"/"bunk"/"classes" -> ALWAYS "attendance_risk", NEVER "academic"
2. "CGPA"/"SGPA"/"GPA"/"grade point"/"target CGPA"/"what if grade" -> ALWAYS "academic"
3. "marks"/"score"/"CAT"/"FAT" -> "academic"
4. "deadline"/"due"/"submission" WITHOUT company context -> "connector"
5. "schedule"/"class"/"today"/"tomorrow" about VIEWING existing timetable -> "connector"
6. "schedule"/"plan" about CREATING a new study plan -> "schedule"
7. Vague queries like "how am I doing", "what's happening" -> ALWAYS "general"
8. If BOTH attendance AND grade/CGPA are mentioned, pick the DOMINANT subject (the one the user wants answered)
9. If genuinely ambiguous between 2+ intents, choose "general"

CONFIDENCE:
- 0.9+: unambiguous, clearly one intent
- 0.7-0.89: slight ambiguity but one intent is clearly stronger
- below 0.7: genuinely ambiguous -- in this case set intent to "general"

Return ONLY a JSON object:
{
  "intent": "<one of: academic, attendance_risk, schedule, action, connector, general>",
  "sub_intent": "<more specific description>",
  "requires_context": ["marks", "attendance", "tasks", "events", "profile", "history", "regulations", "emails"],
  "confidence": <0.0 to 1.0>
}
"""


class OrchestratorAgent(BaseAgent):
    """Central routing agent that manages conversation flow and delegates to specialists."""

    def __init__(self):
        self.academic_agent = AcademicAgent()
        self.schedule_agent = ScheduleAgent()
        self.action_agent = ActionAgent()
        self.connector_agent = ConnectorAgent()
        self.memory = ConversationMemory()

    async def execute(self, payload: dict) -> dict:
        """Process a user message and return an AI response.

        Args:
            payload: {
                "user_message": str,
                "session_id": str (optional, defaults to "default"),
                "window_context": dict | None (optional, {agent: str, data: dict})
            }

        Returns:
            {
                "response": str,
                "intent": str,
                "actions": list[dict],
                "pending_actions": list[dict],
                "panel": str | None,
                "panel_data": dict | None
            }
        """
        print("🔥 ORCHESTRATOR CALLED", flush=True)
        print(f"🔥 PAYLOAD: {payload.get('user_message', '')[:80]}", flush=True)

        user_message = payload["user_message"]
        session_id = payload.get("session_id", "default")
        window_context = payload.get("window_context")

        # Get conversation history
        history = self.memory.get_history(session_id)

        # ─── Window Context Fast-Path: skip intent classification ─────────────
        if window_context and isinstance(window_context, dict):
            result = await self._handle_window_followup(
                user_message, window_context, history, session_id
            )
            self.memory.add_message(session_id, "user", user_message)
            self.memory.add_message(session_id, "assistant", result["response"])
            return result

        # ─── LLM Workflow Planner (feature-flagged) ───────────────────────────
        from app.agents.workflow_planner import USE_WORKFLOW_PLANNER

        if USE_WORKFLOW_PLANNER:
            return await self._execute_planned(user_message, session_id, history)

        # ─── Legacy Path: classify -> gather -> route ───────────────────────────
        return await self._execute_legacy(user_message, session_id, history)

    async def _execute_planned(self, user_message: str, session_id: str, history: list[dict]) -> dict:
        """New LLM-driven workflow: single planner step -> scoped retrieval -> leaf agent."""
        from app.agents.workflow_planner import (
            plan_workflow,
            retrieve_with_condition_resolution,
            OrchestratorContext,
        )

        # Step 1: LLM plans the workflow (agent + data scope + reasoning)
        plan = await plan_workflow(user_message, history)

        # Step 2: Two-pass retrieval -- scoped data + condition resolution
        prefetched_data = await retrieve_with_condition_resolution(plan)

        # Step 3: Build orchestrator context to forward to leaf agent
        orch_context = OrchestratorContext(user_message, plan, prefetched_data)

        # Step 4: Route to the chosen agent with full context
        profile = get_user_profile()
        agent_payload = {
            "user_message": user_message,
            "sub_intent": plan.reasoning,
            "context": prefetched_data,
            "history": history[-10:],
            "profile": profile,
            "orchestrator_context": orch_context.to_dict(),
        }

        if plan.agent == "attendance_risk":
            if "attendance" not in (prefetched_data.get("source") or ""):
                # Ensure attendance data is available
                agent_payload["context"]["attendance"] = prefetched_data.get("attendance", [])
            try:
                result = await self.academic_agent.execute(agent_payload)
            except Exception as e:
                logger.warning("Academic agent failed for attendance: %s -- using data fallback.", e)
                result = self._data_fallback_response(prefetched_data, "attendance")
            intent = "attendance_risk"
        elif plan.agent == "gpa_projection":
            try:
                result = await self.academic_agent.execute(agent_payload)
            except Exception as e:
                logger.warning("Academic agent failed for GPA: %s -- using data fallback.", e)
                result = self._data_fallback_response(prefetched_data, "marks")
            intent = "academic"
        elif plan.agent == "regulations":
            # Regulations are loaded by retrieve_with_condition_resolution;
            # student profile is fetched by Pass 2 if conditions require it.
            regs = self._load_regulations()
            agent_payload["context"]["regulations"] = regs
            result = await self.academic_agent.execute(agent_payload)
            intent = "academic"
        elif plan.agent == "deadlines":
            result = await self.connector_agent.execute(agent_payload)
            intent = "connector"
        elif plan.agent == "placements":
            result = await self.connector_agent.execute(agent_payload)
            intent = "connector"
        elif plan.agent == "timetable":
            result = await self.connector_agent.execute(agent_payload)
            intent = "connector"
        elif plan.agent in ("schedule",):
            result = await self.schedule_agent.execute(agent_payload)
            intent = "schedule"
        elif plan.agent == "action":
            result = await self.action_agent.execute(agent_payload)
            intent = "action"
        elif plan.agent == "connector":
            # WhatsApp/email queries — fetch context and pass to connector agent
            from app.database import async_session_maker
            from sqlmodel import select
            from app.models import EmailNotification
            async with async_session_maker() as session:
                wa_result = await session.exec(
                    select(EmailNotification)
                    .where(EmailNotification.sender.like("WhatsApp:%"))
                    .order_by(EmailNotification.received_at.desc())
                    .limit(50)
                )
                wa_messages = wa_result.all()
                email_result = await session.exec(
                    select(EmailNotification)
                    .where(~EmailNotification.sender.like("WhatsApp:%"))
                    .order_by(EmailNotification.received_at.desc())
                    .limit(30)
                )
                email_messages = email_result.all()

            agent_payload["context"]["whatsapp_messages"] = [
                {
                    "group": (e.sender or "").replace("WhatsApp: ", ""),
                    "message": e.raw_body or "",
                    "date": e.received_at.isoformat() if e.received_at else "",
                    "category": e.category,
                }
                for e in wa_messages
            ]
            agent_payload["context"]["emails"] = [
                {
                    "from": e.sender,
                    "subject": e.subject,
                    "date": e.received_at.isoformat() if e.received_at else "",
                    "category": e.category,
                    "priority": e.priority,
                    "summary": e.summary,
                    "body": (e.raw_body or "")[:500],
                    "is_read": e.is_read,
                }
                for e in email_messages
            ]
            print(f"🔥 CONNECTOR: whatsapp={len(wa_messages)}, emails={len(email_messages)}", flush=True)
            result = await self.connector_agent.execute(agent_payload)
            intent = "connector"
        else:
            # chat / general / unknown
            result = await self._handle_general(agent_payload)
            intent = "general"

        # Step 5: Save memory
        self.memory.add_message(session_id, "user", user_message)
        self.memory.add_message(
            session_id,
            "assistant",
            result["response"],
            metadata={
                "intent": intent,
                "plan": plan.to_dict(),
            },
        )

        return {
            "response": result["response"],
            "intent": intent,
            "sub_intent": plan.reasoning,
            "actions": result.get("actions", []),
            "pending_actions": result.get("pending_actions", []),
            "panel": result.get("panel"),
            "panel_data": result.get("panel_data"),
            "workflow_plan": plan.to_dict(),
        }

    async def _execute_legacy(self, user_message: str, session_id: str, history: list[dict]) -> dict:
        """Legacy rule-based routing (fallback when planner is disabled)."""

        # Step 1: Classify intent
        classification = await self._classify_intent(user_message, history)
        intent = classification.get("intent", "general")
        sub_intent = classification.get("sub_intent", "")
        requires_context = classification.get("requires_context", [])
        confidence = classification.get("confidence", 0.5)

        # Keyword override: force connector for WhatsApp/email queries
        msg_lower = user_message.lower()
        if any(kw in msg_lower for kw in ["whatsapp", "group", "wa group", "messages from"]):
            intent = "connector"
            if "emails" not in requires_context:
                requires_context.append("emails")
            confidence = 0.95
        elif any(kw in msg_lower for kw in ["email", "inbox", "gmail", "mail"]):
            intent = "connector"
            if "emails" not in requires_context:
                requires_context.append("emails")
            confidence = 0.95

        # Enforce confidence threshold -- fall back to general if uncertain
        if confidence < 0.7 and intent != "general":
            logger.info(
                "Low confidence %.2f for intent '%s' -- falling back to general.",
                confidence, intent,
            )
            intent = "general"

        logger.info(
            "Orchestrator classified (legacy): intent=%s, sub_intent=%s, confidence=%.2f",
            intent,
            sub_intent,
            confidence,
        )

        # Step 2: Gather required context
        context = await self._gather_context(requires_context, session_id)

        # Step 3: Route to specialist agent
        agent_payload = {
            "user_message": user_message,
            "sub_intent": sub_intent,
            "context": context,
            "history": history[-10:],
            "profile": get_user_profile(),
        }

        if intent == "academic":
            result = await self.academic_agent.execute(agent_payload)
        elif intent == "attendance_risk":
            if "attendance" not in requires_context:
                requires_context.append("attendance")
                context = await self._gather_context(requires_context, session_id)
                agent_payload["context"] = context
            result = await self.academic_agent.execute(agent_payload)
        elif intent == "schedule":
            result = await self.schedule_agent.execute(agent_payload)
        elif intent == "action":
            result = await self.action_agent.execute(agent_payload)
        elif intent == "connector":
            result = await self.connector_agent.execute(agent_payload)
        else:
            result = await self._handle_general(agent_payload)

        # Step 4: Save to conversation memory
        self.memory.add_message(session_id, "user", user_message)
        self.memory.add_message(
            session_id,
            "assistant",
            result["response"],
            metadata={
                "intent": intent,
                "sub_intent": sub_intent,
                "context_used": requires_context,
            },
        )

        return {
            "response": result["response"],
            "intent": intent,
            "sub_intent": sub_intent,
            "actions": result.get("actions", []),
            "pending_actions": result.get("pending_actions", []),
            "panel": result.get("panel"),
            "panel_data": result.get("panel_data"),
        }

    async def _handle_window_followup(
        self, message: str, window_context: dict, history: list[dict], session_id: str
    ) -> dict:
        """Handle a follow-up question within a specific agent window.

        Skips intent classification, routes directly using the window agent type
        and injects the window current data into the LLM prompt.

        If the question is about policy/regulations (not calculation), injects
        the regulations data so the agent answers from official rules.
        """
        agent_type = window_context.get("agent", "general")
        context_data = window_context.get("data", {})
        profile = get_user_profile()

        # Detect policy/regulation questions vs calculation questions
        lower_msg = message.lower()
        is_policy_question = any(kw in lower_msg for kw in [
            "need to", "required", "mandatory", "what happens if",
            "minimum", "condone", "condonation", "exam eligibility",
            "debarred", "rule", "regulation", "policy", "allowed",
            "do i need", "is it", "what is the",
        ])

        # Load regulations context for policy questions
        regulations_text = ""
        if is_policy_question:
            regs = self._load_regulations()
            if regs:
                # Format relevant section based on agent type
                if agent_type == "attendance_risk":
                    att = regs.get("attendance", {})
                    regulations_text = f"""

IMPORTANT -- VIT OFFICIAL ATTENDANCE REGULATIONS (from FFCS v4.0):
- Minimum Required: {att.get('minimum_required', 75)}% per course
- Rule: {att.get('minimum_required_note', 'N/A')}
- Consequence: {att.get('consequence', 'N/A')}
- 9-Pointer Exemption: {att.get('nine_pointer_exemption', 'N/A')}
- Condonation: {att.get('condonation', 'N/A')}
- CGPA Exemption: {att.get('cgpa_exemption', 'N/A')}
- Calculation: {att.get('calculation', 'N/A')}
- Lab vs Theory: {att.get('lab_vs_theory', 'N/A')}
- Medical Leave: {att.get('medical', 'N/A')}
- On Duty: {att.get('on_duty', 'N/A')}

STUDENT CONTEXT: This student has CGPA 9.11 and no backlogs -- check if the 9-pointer exemption applies to them.

NOTE: The 75% figure in this tool calculator is the same as VIT actual regulation threshold.
Frame your answer from the REGULATION perspective, not the tool internal threshold.
Do NOT fabricate exemptions or rules that are not listed above. Only state what the regulations explicitly say."""
                else:
                    # Generic regulations injection for other agents
                    regulations_text = f"\n\nVIT REGULATIONS DATA:\n{json.dumps(regs, indent=2, default=str)[:2000]}"

        # Build context-rich system prompt
        agent_label = agent_type.replace("_", " ").title()

        threshold_disclaimer = ""
        if agent_type == "attendance_risk":
            threshold_disclaimer = """
IMPORTANT DISTINCTION:
- This tool tracks toward a 75% threshold, which matches VIT actual regulation.
- When the user asks about POLICY (rules, requirements, consequences), answer from the VIT regulations below.
- When the user asks about CALCULATIONS (how many classes, what if I skip), use the data displayed.
- NEVER present an internal tool constant as if it were a regulation without citing the actual rule.
- VIT HAS a 9-pointer exemption: CGPA >= 9.0 + no backlogs = exempted from 75% rule.
- Only state exemptions/rules that are explicitly in the regulations data below."""

        system_prompt = f"""
You are CampusFlow {agent_label} assistant for {profile.get('name', 'the student')}.
They are viewing the {agent_label} window which currently shows the following data:

{json.dumps(context_data, indent=2, default=str)[:3000]}
{threshold_disclaimer}
{regulations_text}

The user is asking a follow-up question about this data or related policy. 
- For CALCULATION questions: use the exact numbers shown above.
- For POLICY/REGULATION questions: answer from the regulations data, citing specific rules.
- Do NOT fabricate rules or exemptions that aren't in the regulations data.
- If the regulations data doesn't cover something, say you don't have that information.
Be concise (under 150 words), helpful, and precise."""

        history_text = ""
        if history:
            recent = history[-4:]
            history_text = "\n".join(
                f"{m['role']}: {m['content'][:200]}" for m in recent
            )

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if history_text:
            messages.append({"role": "user", "content": f"[Recent conversation]\n{history_text}"})
        messages.append({"role": "user", "content": message})

        try:
            response = await chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=512,
            )
        except Exception as e:
            logger.warning("Window follow-up LLM failed: %s", e)
            response = "Sorry, I couldn't process that follow-up. Try rephrasing or ask in the main command bar."

        return {
            "response": response,
            "intent": agent_type,
            "sub_intent": "window_followup",
            "actions": [],
            "pending_actions": [],
            "panel": None,
            "panel_data": None,
        }

    async def _classify_intent(self, message: str, history: list[dict]) -> dict:
        """Use LLM to classify user intent."""
        # Build history context for the classifier
        history_text = ""
        if history:
            recent = history[-6:]  # Last 3 exchanges
            history_text = "\n".join(
                f"{m['role'].upper()}: {m['content'][:200]}" for m in recent
            )

        user_prompt = f"CONVERSATION HISTORY:\n{history_text}\n\nCURRENT MESSAGE: {message}"

        try:
            content = await chat_completion(
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=256,
            )
            return json.loads(content)
        except Exception as e:
            logger.warning("Intent classification failed: %s", e)
            return {"intent": "general", "sub_intent": "", "requires_context": [], "confidence": 0.5}

    async def _gather_context(self, requires: list[str], session_id: str) -> dict:
        """Gather all required context data from DB and memory."""
        from app.database import async_session_maker
        from sqlmodel import select
        from app.models import Attendance, CourseMark, AcademicProfile, Task, Event, Notice, EmailNotification

        context: dict = {}

        async with async_session_maker() as session:
            if "marks" in requires:
                result = await session.exec(
                    select(CourseMark).order_by(CourseMark.course_code)
                )
                marks = result.all()
                context["marks"] = [
                    {
                        "course_code": m.course_code,
                        "course_title": m.course_title,
                        "mark_title": m.mark_title,
                        "max_mark": m.max_mark,
                        "weightage_pct": m.weightage_pct,
                        "score": m.score,
                        "weightage_mark": m.weightage_mark,
                        "status": m.status,
                    }
                    for m in marks
                ]

            if "attendance" in requires:
                result = await session.exec(
                    select(Attendance).order_by(Attendance.course_code)
                )
                attendance = result.all()
                context["attendance"] = [
                    {
                        "course_code": a.course_code,
                        "course_title": a.course_title,
                        "percentage": a.percentage,
                        "attended": a.attended,
                        "total": a.total,
                    }
                    for a in attendance
                ]

            if "tasks" in requires:
                result = await session.exec(
                    select(Task).where(Task.status == "pending").order_by(Task.deadline)
                )
                tasks = result.all()
                context["tasks"] = [
                    {
                        "title": t.title,
                        "deadline": t.deadline.isoformat(),
                        "status": t.status,
                        "is_conflict": t.is_conflict,
                    }
                    for t in tasks
                ]

            if "events" in requires:
                result = await session.exec(
                    select(Event).order_by(Event.start_time.desc()).limit(20)
                )
                events = result.all()
                context["events"] = [
                    {
                        "title": e.title,
                        "start_time": e.start_time.isoformat(),
                        "end_time": e.end_time.isoformat(),
                        "location": e.location,
                    }
                    for e in events
                ]

            if "profile" in requires:
                result = await session.exec(
                    select(AcademicProfile).order_by(AcademicProfile.updated_at.desc()).limit(1)
                )
                profile = result.first()
                if profile:
                    context["academic_profile"] = {
                        "cgpa": profile.cgpa,
                        "total_credits": profile.total_credits,
                        "overall_attendance": profile.overall_attendance,
                        "semester_name": profile.semester_name,
                    }

            if "emails" in requires:
                result = await session.exec(
                    select(EmailNotification)
                    .order_by(EmailNotification.received_at.desc())
                    .limit(30)
                )
                emails = result.all()
                context["emails"] = [
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

            # Always fetch WhatsApp messages for connector intent
            wa_result = await session.exec(
                select(EmailNotification)
                .where(EmailNotification.sender.like("WhatsApp:%"))
                .order_by(EmailNotification.received_at.desc())
                .limit(50)
            )
            wa_messages = wa_result.all()
            if wa_messages:
                context["whatsapp_messages"] = [
                    {
                        "group": (e.sender or "").replace("WhatsApp: ", ""),
                        "message": e.raw_body or "",
                        "date": e.received_at.isoformat() if e.received_at else "",
                        "category": e.category,
                    }
                    for e in wa_messages
                ]

        # Debug: log context sizes
        email_count = len(context.get("emails", []))
        wa_count = len(context.get("whatsapp_messages", []))
        logger.info("Context built: emails=%d, whatsapp=%d, requires=%s", email_count, wa_count, requires)

        if "history" in requires:
            context["conversation_summary"] = self.memory.get_summary(session_id)

        if "regulations" in requires:
            context["regulations"] = self._load_regulations()

        return context

    def _load_regulations(self) -> dict:
        """Load VIT academic regulations from fabricated data."""
        import json
        from pathlib import Path

        reg_file = Path(__file__).resolve().parent.parent.parent / "data" / "fabricated" / "academic_regulations.json"
        if reg_file.exists():
            with open(reg_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    async def _handle_general(self, payload: dict) -> dict:
        """Handle general conversation with full context awareness."""
        profile = payload["profile"]
        history = payload["history"]

        history_text = ""
        if history:
            recent = history[-6:]
            history_text = "\n".join(
                f"{m['role']}: {m['content'][:300]}" for m in recent
            )

        system_prompt = f"""\
You are CampusFlow, a campus assistant for {profile.get('name', 'the student')}.
They study {profile.get('branch', 'CSE')} at VIT Chennai, CGPA {profile.get('cgpa', 'N/A')}.

CRITICAL RULES:
- Never invent WhatsApp groups, emails, or any data not explicitly provided below.
- If asked about WhatsApp groups/messages and no data is provided, say: "Let me check your WhatsApp messages" and suggest asking again so I can route to the correct agent.
- If asked about emails, attendance, marks -- say "Let me look that up" and suggest a specific query.
- Do NOT use profile interests to guess/invent group names or email subjects.

CONVERSATION HISTORY:
{history_text}"""

        try:
            response = await chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": payload["user_message"]},
                ],
                temperature=0.7,
                max_tokens=512,
            )
        except Exception as e:
            logger.warning("General chat LLM failed: %s", e)
            response = f"Hey {profile.get('name', 'there')}! I'm here to help with your academics, schedule, reminders, and more. What would you like to know?"

        return {
            "response": response,
            "actions": [
                {"label": "Check my marks", "type": "reply"},
                {"label": "Create a study plan", "type": "reply"},
                {"label": "Set a reminder", "type": "reply"},
            ],
        }

    def _data_fallback_response(self, prefetched_data: dict, data_key: str) -> dict:
        """Generate a plain-text response from prefetched data when LLM is unavailable.

        Falls back to formatting the raw data directly rather than returning
        a useless generic greeting.
        """
        data = prefetched_data.get(data_key, [])

        if not data:
            return {
                "response": f"I found your {data_key} data but it appears to be empty. Try syncing VTOP first.",
                "actions": [],
            }

        if data_key == "attendance":
            lines = ["Here's your attendance data:\n"]
            for a in data:
                lines.append(
                    f"• {a['course_code']}: {a['percentage']}% "
                    f"({a['attended']}/{a['total']} classes)"
                )
            return {"response": "\n".join(lines), "actions": []}

        if data_key == "marks":
            lines = ["Here's your marks data:\n"]
            for m in data:
                score_str = f"{m['score']}" if m.get('score') is not None else "N/A"
                lines.append(f"• {m['course_code']} -- {m['mark_title']}: {score_str}")
            return {"response": "\n".join(lines), "actions": []}

        # Generic fallback: dump as text
        import json
        return {
            "response": f"Here's the data I retrieved:\n\n{json.dumps(data, indent=2, default=str)[:2000]}",
            "actions": [],
        }

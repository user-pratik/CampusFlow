"""Orchestrator Agent — Routes user queries to specialist agents and maintains conversation memory.

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

- "academic": Questions about marks, grades, CGPA, attendance, course performance, improvement tips, academic regulations, exam schedule, grading policy, credit requirements, passing criteria, FFCS rules, withdrawal, add/drop, backlogs, minors, honours
- "schedule": Requests to create study plans, daily schedules, task checklists, time management
- "action": Requests to set alarms, send messages, open assignments, create reminders, or any actionable task
- "connector": Questions about WhatsApp messages, group chats, emails, inbox, calendar events, timetable, deadlines, upcoming exams, study groups, class schedule, what's due
- "general": General conversation, greetings, or queries that don't fit above categories

Return ONLY a JSON object with:
{
  "intent": "<one of: academic, schedule, action, connector, general>",
  "sub_intent": "<more specific description of what user wants>",
  "requires_context": ["marks", "attendance", "tasks", "events", "profile", "history", "regulations"],
  "confidence": <0.0 to 1.0>
}

The "requires_context" field should list what data the specialist agent will need.
If the query builds on previous conversation (e.g., "create a schedule based on that"), include "history".
If the query is about messages, emails, or calendar, use "connector" intent.
If the query mentions academic rules, policies, FFCS, grading, credits, attendance rules, exams schedule, withdrawal, include "regulations" in requires_context.
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
                "session_id": str (optional, defaults to "default")
            }

        Returns:
            {
                "response": str,
                "intent": str,
                "actions": list[dict],  # suggested UI actions
                "pending_actions": list[dict],  # actions queued for execution
                "panel": str | None,
                "panel_data": dict | None
            }
        """
        user_message = payload["user_message"]
        session_id = payload.get("session_id", "default")

        # Get conversation history
        history = self.memory.get_history(session_id)

        # Step 1: Classify intent
        classification = await self._classify_intent(user_message, history)
        intent = classification.get("intent", "general")
        sub_intent = classification.get("sub_intent", "")
        requires_context = classification.get("requires_context", [])

        logger.info(
            "Orchestrator classified: intent=%s, sub_intent=%s, confidence=%.2f",
            intent,
            sub_intent,
            classification.get("confidence", 0),
        )

        # Step 2: Gather required context
        context = await self._gather_context(requires_context, session_id)

        # Step 3: Route to specialist agent
        agent_payload = {
            "user_message": user_message,
            "sub_intent": sub_intent,
            "context": context,
            "history": history[-10:],  # Last 10 messages for context
            "profile": get_user_profile(),
        }

        if intent == "academic":
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

        # Step 5: Return structured response
        return {
            "response": result["response"],
            "intent": intent,
            "sub_intent": sub_intent,
            "actions": result.get("actions", []),
            "pending_actions": result.get("pending_actions", []),
            "panel": result.get("panel"),
            "panel_data": result.get("panel_data"),
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
        from app.models import Attendance, CourseMark, AcademicProfile, Task, Event, Notice

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
You are CampusFlow, a friendly and intelligent campus assistant for {profile.get('name', 'the student')}.
You know they study {profile.get('branch', 'CS')} at {profile.get('college', 'VIT')}.
Their interests are: {', '.join(profile.get('interests', []))}.
Current focus: {profile.get('current_focus', 'general studies')}.

Be warm, concise, and helpful. If they ask something you can help with (marks, schedule, reminders), 
offer to do that. Keep responses under 150 words unless detail is needed.

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

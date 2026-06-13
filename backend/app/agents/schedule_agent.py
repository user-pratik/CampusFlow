"""Schedule Agent — Creates personalized study plans and daily task checklists.

This agent:
- Creates daily/weekly study schedules based on academic performance
- Prioritizes weak subjects (from marks data) 
- Considers student's interests and current focus
- Generates task checklists with time blocks
- Remembers past discussions (e.g., if student mentioned bad marks, uses that info)
- Outputs structured schedule data + natural language explanation
"""

import json
import logging
from datetime import datetime

from app.agents.base import BaseAgent
from app.agents.action_agent import ActionAgent
from app.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

SCHEDULE_SYSTEM_PROMPT = """\
You are CampusFlow's Schedule Planner agent for {name}, a {branch} student at {college}.
Their interests: {interests}. Current focus: {current_focus}.

You create personalized study schedules and daily task checklists based on their actual academic data.

GUIDELINES:
- Use their marks to identify weak subjects that need more study time
- Consider their attendance (low attendance subjects need in-class focus)
- Factor in upcoming deadlines/tasks if any
- Balance study with breaks (Pomodoro-style: 25 min study, 5 min break)
- Allocate more time to subjects with lower scores
- Include their interests as motivational breaks (e.g., "30 min AI project" between study blocks)
- Be realistic — don't overschedule
- If they have pending tasks/deadlines, prioritize those

CONVERSATION HISTORY:
{history}

ACADEMIC DATA:
{academic_data}

PENDING TASKS:
{tasks_data}

TODAY: {today}

OUTPUT FORMAT:
Respond naturally explaining the schedule, then include a JSON block wrapped in ```json ... ``` 
with this structure:
{{
  "schedule_type": "daily" or "weekly",
  "date": "YYYY-MM-DD",
  "blocks": [
    {{
      "time": "HH:MM - HH:MM",
      "activity": "description",
      "subject": "course code or null",
      "priority": "high" | "medium" | "low",
      "duration_minutes": 30
    }}
  ],
  "daily_goals": ["goal 1", "goal 2"],
  "weekly_focus": ["subject 1 — reason", "subject 2 — reason"]
}}

Make the natural language response conversational and motivating. The JSON block is for 
the system to create actionable reminders automatically.
"""


class ScheduleAgent(BaseAgent):
    """Creates personalized study schedules and task checklists."""

    def __init__(self):
        self.action_agent = ActionAgent()

    async def execute(self, payload: dict) -> dict:
        """Generate a study schedule or task checklist.

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
                "pending_actions": list[dict],
                "panel": str | None,
                "panel_data": dict | None
            }
        """
        user_message = payload["user_message"]
        context = payload["context"]
        history = payload["history"]
        profile = payload["profile"]

        # Build context strings
        academic_data = self._format_academic_context(context)
        tasks_data = self._format_tasks(context)
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:300]}" for m in history[-8:]
        ) if history else "No prior conversation."

        system_prompt = SCHEDULE_SYSTEM_PROMPT.format(
            name=profile.get("name", "Student"),
            branch=profile.get("branch", "CS"),
            college=profile.get("college", "VIT"),
            interests=", ".join(profile.get("interests", [])),
            current_focus=profile.get("current_focus", "studies"),
            history=history_text,
            academic_data=academic_data,
            tasks_data=tasks_data,
            today=datetime.now().strftime("%A, %B %d, %Y"),
        )

        try:
            response = await chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.6,
                max_tokens=1500,
            )
        except Exception as e:
            logger.warning("ScheduleAgent LLM call failed: %s", e)
            response = "I couldn't create your schedule right now. Let me try again in a moment."
            return {"response": response, "actions": [], "pending_actions": []}

        # Extract JSON schedule block if present
        schedule_data = self._extract_schedule_json(response)
        pending_actions = []

        # If we got structured schedule data, create action items
        if schedule_data:
            pending_actions = await self._create_schedule_actions(schedule_data, profile)
            # Clean the JSON block from the user-facing response
            response = self._clean_response(response)

        actions = [
            {"label": "Set reminders for this schedule", "type": "reply"},
            {"label": "Adjust — more free time", "type": "reply"},
            {"label": "Show my calendar", "type": "navigate", "payload": "calendar"},
        ]

        return {
            "response": response,
            "actions": actions,
            "pending_actions": pending_actions,
            "panel": "calendar",
            "panel_data": {"schedule": schedule_data} if schedule_data else None,
        }

    def _format_academic_context(self, context: dict) -> str:
        """Format marks and attendance for the schedule prompt."""
        parts = []

        if "academic_profile" in context:
            ap = context["academic_profile"]
            parts.append(f"CGPA: {ap['cgpa']} | Credits: {ap['total_credits']}")

        if "marks" in context and context["marks"]:
            # Group by course, calculate totals
            course_totals: dict[str, dict] = {}
            for m in context["marks"]:
                key = m["course_code"]
                if key not in course_totals:
                    course_totals[key] = {
                        "title": m["course_title"],
                        "total_weighted": 0,
                        "assessments": 0,
                    }
                course_totals[key]["total_weighted"] += m["weightage_mark"] or 0
                course_totals[key]["assessments"] += 1

            parts.append("\nCourse Performance (by weighted marks):")
            sorted_courses = sorted(
                course_totals.items(), key=lambda x: x[1]["total_weighted"]
            )
            for code, data in sorted_courses:
                level = (
                    "🟢 Strong"
                    if data["total_weighted"] >= 35
                    else "🟡 Average"
                    if data["total_weighted"] >= 25
                    else "🔴 Weak"
                )
                parts.append(
                    f"  {level} {code} ({data['title']}): "
                    f"{data['total_weighted']:.1f} weighted marks from {data['assessments']} assessments"
                )

        if "attendance" in context and context["attendance"]:
            low_att = [a for a in context["attendance"] if a["percentage"] < 80]
            if low_att:
                parts.append("\n⚠️ Low attendance subjects (need in-class focus):")
                for a in low_att:
                    parts.append(f"  {a['course_code']}: {a['percentage']}%")

        return "\n".join(parts) if parts else "No academic data available."

    def _format_tasks(self, context: dict) -> str:
        """Format pending tasks."""
        if "tasks" not in context or not context["tasks"]:
            return "No pending tasks."

        lines = []
        for t in context["tasks"]:
            conflict = " ⚠️ CONFLICT" if t["is_conflict"] else ""
            lines.append(f"  - {t['title']} (due: {t['deadline']}){conflict}")
        return "\n".join(lines)

    def _extract_schedule_json(self, response: str) -> dict | None:
        """Extract JSON block from LLM response."""
        try:
            # Look for ```json ... ``` block
            if "```json" in response:
                start = response.index("```json") + 7
                end = response.index("```", start)
                json_str = response[start:end].strip()
                return json.loads(json_str)
            # Try to find raw JSON object
            elif '{"schedule_type"' in response:
                start = response.index('{"schedule_type"')
                # Find matching closing brace
                depth = 0
                for i, c in enumerate(response[start:], start):
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            json_str = response[start : i + 1]
                            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            logger.debug("Could not extract schedule JSON: %s", e)
        return None

    def _clean_response(self, response: str) -> str:
        """Remove JSON block from user-facing response."""
        if "```json" in response:
            start = response.index("```json")
            end = response.index("```", start + 7) + 3
            response = response[:start].rstrip() + response[end:].lstrip()
        return response.strip()

    async def _create_schedule_actions(self, schedule: dict, profile: dict) -> list[dict]:
        """Convert schedule blocks into queued action items."""
        pending = []

        blocks = schedule.get("blocks", [])
        date = schedule.get("date", datetime.now().strftime("%Y-%m-%d"))

        for block in blocks:
            if block.get("priority") in ("high", "medium"):
                action = {
                    "type": "reminder",
                    "title": block["activity"],
                    "time": f"{date}T{block['time'].split(' - ')[0]}:00",
                    "duration_minutes": block.get("duration_minutes", 30),
                    "subject": block.get("subject"),
                    "priority": block.get("priority", "medium"),
                }
                pending.append(action)

        # Save schedule actions via ActionAgent
        if pending:
            await self.action_agent.execute({
                "user_message": "Save schedule",
                "sub_intent": "save_schedule",
                "action_type": "schedule",
                "actions": pending,
                "context": {},
                "history": [],
                "profile": profile,
            })

        return pending

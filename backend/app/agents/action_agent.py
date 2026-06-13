"""Action Agent — Produces structured JSON action files for future integration.

This agent handles all actionable requests:
- Setting alarms/reminders
- Sending WhatsApp messages
- Opening assignments
- Creating calendar events
- Any other executable action

Actions are stored as JSON files in backend/data/actions/ for later integration
with real services (alarm system, WhatsApp API, assignment portal, etc.).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.agents.base import BaseAgent
from app.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

# Action queue directory
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIONS_DIR = BACKEND_ROOT / "data" / "actions"
ACTIONS_DIR.mkdir(parents=True, exist_ok=True)

ACTION_SYSTEM_PROMPT = """\
You are CampusFlow's Action Executor agent for {name}.

Your job is to parse action requests and produce structured action data.
The user may ask to:
- Set an alarm or reminder (for class, exam, deadline, etc.)
- Send a WhatsApp message to someone
- Open an assignment or portal link
- Create a calendar event
- Set a recurring reminder (e.g., "remind me every day at 8am to study")
- Mark a task as done

Given the user's request and context, produce a JSON response with:
{{
  "actions": [
    {{
      "id": "<unique-id>",
      "type": "<alarm | reminder | whatsapp_message | open_link | calendar_event | task_update | recurring_reminder>",
      "status": "pending",
      "created_at": "<ISO datetime>",
      "data": {{
        // Type-specific fields (see below)
      }},
      "display_text": "<human-readable description of the action>"
    }}
  ],
  "confirmation_message": "<what to say to the user confirming the action>"
}}

TYPE-SPECIFIC DATA FIELDS:

alarm:
  "time": "HH:MM",
  "date": "YYYY-MM-DD",
  "label": "description",
  "repeat": "none" | "daily" | "weekdays" | "weekly"

reminder:
  "time": "HH:MM",
  "date": "YYYY-MM-DD",
  "message": "reminder text",
  "priority": "high" | "medium" | "low"

whatsapp_message:
  "recipient": "name or number",
  "message": "text to send",
  "group": "group name if applicable"

open_link:
  "url": "the URL to open",
  "label": "description",
  "portal": "vtop" | "lms" | "email" | "other"

calendar_event:
  "title": "event name",
  "date": "YYYY-MM-DD",
  "start_time": "HH:MM",
  "end_time": "HH:MM",
  "location": "place",
  "description": "details"

task_update:
  "task_id": "if known",
  "title": "task name",
  "new_status": "completed" | "in_progress" | "cancelled"

recurring_reminder:
  "time": "HH:MM",
  "message": "reminder text",
  "frequency": "daily" | "weekdays" | "weekly" | "custom",
  "days": ["Monday", "Wednesday"] (for custom)

CONVERSATION HISTORY:
{history}

TODAY: {today}
CURRENT TIME: {current_time}

If the user's request is vague (e.g., "remind me tomorrow"), use reasonable defaults.
"Tomorrow" means the next day from TODAY. "Morning" = 08:00, "Evening" = 18:00.
"""


class ActionAgent(BaseAgent):
    """Processes action requests and saves them as structured JSON files."""

    async def execute(self, payload: dict) -> dict:
        """Process an action request.

        Args:
            payload: {
                "user_message": str,
                "sub_intent": str,
                "context": dict,
                "history": list[dict],
                "profile": dict,
                # For programmatic calls from ScheduleAgent:
                "action_type": str (optional),
                "actions": list[dict] (optional)
            }

        Returns:
            {
                "response": str,
                "actions": list[dict],  # UI suggested actions
                "pending_actions": list[dict],  # Queued action items
            }
        """
        # Programmatic call (from ScheduleAgent)
        if payload.get("action_type") == "schedule" and payload.get("actions"):
            return await self._save_programmatic_actions(payload["actions"], "schedule")

        user_message = payload["user_message"]
        history = payload["history"]
        profile = payload["profile"]

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:200]}" for m in history[-6:]
        ) if history else "No prior conversation."

        now = datetime.now()
        system_prompt = ACTION_SYSTEM_PROMPT.format(
            name=profile.get("name", "Student"),
            history=history_text,
            today=now.strftime("%A, %B %d, %Y"),
            current_time=now.strftime("%H:%M"),
        )

        try:
            content = await chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1024,
            )
            result = json.loads(content)
        except Exception as e:
            logger.warning("ActionAgent LLM call failed: %s", e)
            return {
                "response": "I understood you want me to do something, but I had trouble processing it. Could you rephrase?",
                "actions": [{"label": "Try again", "type": "reply"}],
                "pending_actions": [],
            }

        # Save actions to disk
        actions = result.get("actions", [])
        saved_actions = []
        for action in actions:
            saved = self._save_action(action)
            saved_actions.append(saved)

        confirmation = result.get(
            "confirmation_message",
            "Done! I've queued that action for you.",
        )

        # Build UI actions
        ui_actions = [
            {"label": "Show pending actions", "type": "navigate", "payload": "calendar"},
        ]
        if any(a.get("type") == "alarm" or a.get("type") == "reminder" for a in actions):
            ui_actions.append({"label": "Edit reminder", "type": "reply"})
        if any(a.get("type") == "whatsapp_message" for a in actions):
            ui_actions.append({"label": "Open WhatsApp", "type": "navigate", "payload": "whatsapp"})

        return {
            "response": confirmation,
            "actions": ui_actions,
            "pending_actions": saved_actions,
        }

    def _save_action(self, action: dict) -> dict:
        """Save a single action to the actions directory."""
        # Ensure required fields
        if "id" not in action:
            action["id"] = str(uuid4())[:8]
        if "status" not in action:
            action["status"] = "pending"
        if "created_at" not in action:
            action["created_at"] = datetime.now().isoformat()

        # Save individual action file
        filename = f"{action['type']}_{action['id']}.json"
        filepath = ACTIONS_DIR / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(action, f, indent=2, default=str)

        logger.info("Saved action: %s -> %s", action["type"], filepath.name)

        # Also append to the master action log
        self._append_to_log(action)

        return action

    def _append_to_log(self, action: dict) -> None:
        """Append action to the master action log for easy querying."""
        log_file = ACTIONS_DIR / "action_log.json"

        try:
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    log = json.load(f)
            else:
                log = []

            log.append(action)

            # Keep last 100 actions
            if len(log) > 100:
                log = log[-100:]

            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log, f, indent=2, default=str)
        except Exception as e:
            logger.warning("Failed to update action log: %s", e)

    async def _save_programmatic_actions(
        self, actions: list[dict], source: str
    ) -> dict:
        """Save actions from other agents (e.g., ScheduleAgent)."""
        saved = []
        for action_data in actions:
            action = {
                "id": str(uuid4())[:8],
                "type": action_data.get("type", "reminder"),
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "source": source,
                "data": action_data,
                "display_text": action_data.get("title", "Scheduled item"),
            }
            self._save_action(action)
            saved.append(action)

        return {
            "response": f"Saved {len(saved)} action items.",
            "actions": [],
            "pending_actions": saved,
        }

    @staticmethod
    def get_pending_actions() -> list[dict]:
        """Retrieve all pending actions from disk."""
        log_file = ACTIONS_DIR / "action_log.json"
        if not log_file.exists():
            return []

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                log = json.load(f)
            return [a for a in log if a.get("status") == "pending"]
        except Exception:
            return []

    @staticmethod
    def mark_action_done(action_id: str) -> bool:
        """Mark an action as completed."""
        log_file = ACTIONS_DIR / "action_log.json"
        if not log_file.exists():
            return False

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                log = json.load(f)

            for action in log:
                if action.get("id") == action_id:
                    action["status"] = "completed"
                    action["completed_at"] = datetime.now().isoformat()
                    break
            else:
                return False

            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log, f, indent=2, default=str)
            return True
        except Exception:
            return False

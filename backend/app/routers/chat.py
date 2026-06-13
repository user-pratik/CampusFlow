"""Chat router — Main conversational AI endpoint.

Exposes the Orchestrator Agent via a simple POST /api/chat endpoint.
Also provides endpoints for action management and session control.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.orchestrator import OrchestratorAgent
from app.agents.action_agent import ActionAgent

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton orchestrator (holds conversation memory)
_orchestrator = OrchestratorAgent()


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    response: str
    intent: str
    sub_intent: str = ""
    actions: list[dict] = []
    pending_actions: list[dict] = []
    panel: str | None = None
    panel_data: dict | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a user message through the agentic pipeline.

    The orchestrator:
    1. Classifies intent (academic, schedule, action, general)
    2. Gathers relevant context from DB
    3. Routes to specialist agent
    4. Maintains conversation memory for multi-turn interactions

    Examples:
        - "What are my marks in probability?" → AcademicAgent
        - "Create a study schedule for me" → ScheduleAgent
        - "Set an alarm for 7am tomorrow" → ActionAgent
        - "Hey, how's it going?" → General handler
    """
    result = await _orchestrator.execute({
        "user_message": request.message,
        "session_id": request.session_id,
    })

    return ChatResponse(
        response=result["response"],
        intent=result["intent"],
        sub_intent=result.get("sub_intent", ""),
        actions=result.get("actions", []),
        pending_actions=result.get("pending_actions", []),
        panel=result.get("panel"),
        panel_data=result.get("panel_data"),
    )


@router.get("/chat/actions")
async def get_pending_actions() -> dict:
    """Return all pending action items (alarms, reminders, messages, etc.)."""
    actions = ActionAgent.get_pending_actions()
    return {"actions": actions, "count": len(actions)}


@router.post("/chat/actions/{action_id}/complete")
async def complete_action(action_id: str) -> dict:
    """Mark an action as completed."""
    success = ActionAgent.mark_action_done(action_id)
    if success:
        return {"status": "completed", "action_id": action_id}
    return {"status": "not_found", "action_id": action_id}


@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str) -> dict:
    """Return conversation history for a session."""
    history = _orchestrator.memory.get_history(session_id)
    return {
        "session_id": session_id,
        "messages": history,
        "count": len(history),
    }


@router.delete("/chat/history/{session_id}")
async def clear_chat_history(session_id: str) -> dict:
    """Clear conversation history for a session."""
    _orchestrator.memory.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}

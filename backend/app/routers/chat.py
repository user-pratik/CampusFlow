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
    window_context: dict | None = None  # {agent: str, data: dict} for in-window follow-ups


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

    If window_context is provided, the message is treated as a follow-up
    within a specific agent window — skipping intent classification and
    routing directly to the relevant agent with the window's current data.
    """
    result = await _orchestrator.execute({
        "user_message": request.message,
        "session_id": request.session_id,
        "window_context": request.window_context,
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


# ─── Lightweight Intent Classification Endpoint ───────────────────────────────


class ClassifyRequest(BaseModel):
    """Request body for intent classification."""
    message: str


class ClassifyResponse(BaseModel):
    """Response with routing decision for the frontend."""
    agent: str  # attendance_risk, gpa_projection, deadlines, placements, timetable, regulations, chat
    action: str  # spawn_window, chat_only, spawn_and_answer
    confidence: float
    reasoning: str


@router.post("/chat/classify", response_model=ClassifyResponse)
async def classify_intent(request: ClassifyRequest) -> ClassifyResponse:
    """Classify user message intent using the LLM workflow planner.

    Returns which agent window to spawn (or chat fallback) without
    actually executing the agent — used by the frontend command palette
    to decide routing before committing to a window.
    """
    from app.agents.workflow_planner import USE_WORKFLOW_PLANNER, plan_workflow

    if USE_WORKFLOW_PLANNER:
        plan = await plan_workflow(request.message, [])
        return ClassifyResponse(
            agent=plan.agent,
            action=plan.action,
            confidence=plan.confidence,
            reasoning=plan.reasoning,
        )
    else:
        # Fallback: use the legacy classifier
        classification = await _orchestrator._classify_intent(request.message, [])
        intent = classification.get("intent", "general")
        confidence = classification.get("confidence", 0.5)

        # Map legacy intents to agent names
        agent_map = {
            "academic": "gpa_projection",
            "attendance_risk": "attendance_risk",
            "connector": "chat",
            "schedule": "chat",
            "action": "chat",
            "general": "chat",
        }

        return ClassifyResponse(
            agent=agent_map.get(intent, "chat"),
            action="spawn_window" if confidence >= 0.7 and intent not in ("general", "action") else "chat_only",
            confidence=confidence,
            reasoning=classification.get("sub_intent", ""),
        )

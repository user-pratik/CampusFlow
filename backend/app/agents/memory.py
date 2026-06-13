"""Conversation Memory — Maintains multi-turn conversation history per session.

Stores messages in-memory with metadata for context-aware responses.
Provides summarization of past conversation for long-running sessions.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Persist conversation memory to disk for crash recovery
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = BACKEND_ROOT / "data" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


class ConversationMemory:
    """In-memory conversation store with disk persistence and summarization."""

    def __init__(self):
        self._sessions: dict[str, list[dict]] = {}
        self._load_from_disk()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a message to the conversation history.

        Args:
            session_id: Unique session identifier.
            role: "user" or "assistant".
            content: Message text.
            metadata: Optional dict with intent, context_used, etc.
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        self._sessions[session_id].append(message)

        # Keep max 50 messages per session (trim oldest)
        if len(self._sessions[session_id]) > 50:
            self._sessions[session_id] = self._sessions[session_id][-50:]

        # Persist to disk
        self._save_session(session_id)

    def get_history(self, session_id: str) -> list[dict]:
        """Get full conversation history for a session.

        Returns:
            List of message dicts with role, content, timestamp, metadata.
        """
        return self._sessions.get(session_id, [])

    def get_summary(self, session_id: str) -> str:
        """Get a text summary of the conversation for context injection.

        Returns a compact representation of key facts learned during conversation.
        """
        history = self._sessions.get(session_id, [])
        if not history:
            return "No prior conversation."

        # Extract key facts from metadata
        facts = []
        for msg in history:
            meta = msg.get("metadata", {})
            if meta.get("intent") == "academic":
                facts.append(f"Discussed academics: {meta.get('sub_intent', '')}")
            elif meta.get("intent") == "schedule":
                facts.append(f"Discussed scheduling: {meta.get('sub_intent', '')}")
            elif meta.get("intent") == "action":
                facts.append(f"Requested action: {meta.get('sub_intent', '')}")

        # Build summary
        summary_parts = []
        summary_parts.append(f"Conversation has {len(history)} messages.")

        if facts:
            unique_facts = list(dict.fromkeys(facts))  # Deduplicate preserving order
            summary_parts.append("Topics covered: " + "; ".join(unique_facts[-5:]))

        # Include last few user messages for immediate context
        recent_user = [m for m in history[-6:] if m["role"] == "user"]
        if recent_user:
            summary_parts.append(
                "Recent questions: "
                + " | ".join(m["content"][:100] for m in recent_user[-3:])
            )

        return "\n".join(summary_parts)

    def get_context_for_agent(self, session_id: str, intent: str) -> dict:
        """Extract relevant context from history for a specific agent type.

        Searches past messages for data that the agent might need.
        For example, if schedule agent needs marks data, we look for past
        academic agent responses that contained marks info.
        """
        history = self._sessions.get(session_id, [])
        context = {"relevant_history": []}

        for msg in history:
            meta = msg.get("metadata", {})
            # If this assistant message was from the same intent domain
            if msg["role"] == "assistant" and meta.get("intent") == intent:
                context["relevant_history"].append({
                    "content": msg["content"][:500],
                    "sub_intent": meta.get("sub_intent", ""),
                })

        return context

    def clear_session(self, session_id: str) -> None:
        """Clear all messages for a session."""
        self._sessions.pop(session_id, None)
        session_file = MEMORY_DIR / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()

    def _save_session(self, session_id: str) -> None:
        """Persist session to disk."""
        try:
            session_file = MEMORY_DIR / f"{session_id}.json"
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(self._sessions[session_id], f, indent=2, default=str)
        except Exception as e:
            logger.warning("Failed to persist session %s: %s", session_id, e)

    def _load_from_disk(self) -> None:
        """Load all sessions from disk on startup."""
        try:
            for session_file in MEMORY_DIR.glob("*.json"):
                session_id = session_file.stem
                with open(session_file, "r", encoding="utf-8") as f:
                    self._sessions[session_id] = json.load(f)
            if self._sessions:
                logger.info("Loaded %d conversation sessions from disk.", len(self._sessions))
        except Exception as e:
            logger.warning("Failed to load sessions from disk: %s", e)

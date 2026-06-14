"""Group chat payload normalizer.

STATUS: SKELETON — awaiting real sample payloads.

Follows the same pattern as connectors/whatsapp.py:
  extract_text_and_group(payload) → (raw_text, source_group)

Once the real data source is connected:
1. Capture sample payloads and save to sample_payloads.json
2. Implement the parsing logic below based on actual structure
3. Set GROUPCHAT_ENABLED=true in .env
"""

import logging
import os

logger = logging.getLogger(__name__)

GROUPCHAT_ENABLED = os.getenv("GROUPCHAT_ENABLED", "false").lower() == "true"


def extract_text_and_group(payload: dict) -> tuple[str, str]:
    """Normalize an incoming group chat payload to (raw_text, source_group).

    This function MUST be rewritten against real payloads.
    Current implementation is a pass-through placeholder.

    Args:
        payload: Raw webhook/message payload from the group chat source.

    Returns:
        Tuple of (message_text, group_identifier)
    """
    if not GROUPCHAT_ENABLED:
        logger.debug("Group chat connector disabled — GROUPCHAT_ENABLED is false.")
        return "", ""

    # ─── PLACEHOLDER: Replace with real parsing once payload format is known ───
    #
    # Expected to handle something like:
    # {
    #     "message": { "text": "...", "from": "..." },
    #     "chat": { "id": "...", "title": "CSE Batch 2027" },
    #     "timestamp": 1718234400
    # }
    #
    # Actual format TBD — DO NOT assume structure.

    raw_text = payload.get("text", payload.get("message", {}).get("text", ""))
    source_group = payload.get("group", payload.get("chat", {}).get("title", "unknown"))

    return raw_text, source_group

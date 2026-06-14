"""Group chat message processor — routes classified messages to appropriate agents.

STATUS: SKELETON — awaiting real data source.

Once activated, this module:
1. Receives raw payloads (from a webhook or polling mechanism)
2. Normalizes via normalizer.extract_text_and_group()
3. Classifies via classifier.classify_group_message()
4. Routes to:
   - Deadline aggregator (DEADLINE/EXAM/FEE categories)
   - Placement agent (PLACEMENT category)
   - Notice pipeline (ANNOUNCEMENT/EVENT categories)

Call process_group_message(payload) from whatever webhook/polling
mechanism delivers group chat data.
"""

import logging
from datetime import datetime

from app.connectors.groupchat.classifier import classify_group_message
from app.connectors.groupchat.normalizer import GROUPCHAT_ENABLED, extract_text_and_group

logger = logging.getLogger(__name__)


async def process_group_message(payload: dict) -> dict:
    """Process a single incoming group chat message.

    Args:
        payload: Raw message payload from the group chat source.

    Returns:
        Dict with processing result: {status, category, action_taken}
    """
    if not GROUPCHAT_ENABLED:
        return {"status": "disabled", "category": None, "action_taken": None}

    # Step 1: Normalize
    raw_text, source_group = extract_text_and_group(payload)
    if not raw_text:
        return {"status": "empty", "category": None, "action_taken": None}

    # Step 2: Classify
    classification = classify_group_message(raw_text, source_group)
    category = classification["category"]

    if not classification["is_actionable"]:
        return {"status": "skipped", "category": category, "action_taken": None}

    # Step 3: Route to appropriate agent
    action_taken = None

    if category in ("DEADLINE", "EXAM", "FEE"):
        action_taken = await _route_to_deadline_agent(raw_text, source_group, category)

    elif category == "PLACEMENT":
        action_taken = await _route_to_placement_agent(raw_text, source_group)

    elif category in ("ANNOUNCEMENT", "EVENT"):
        action_taken = await _route_to_notice_pipeline(raw_text, source_group, category)

    logger.info(
        "Processed group message from '%s': category=%s, action=%s",
        source_group, category, action_taken,
    )
    return {"status": "processed", "category": category, "action_taken": action_taken}


async def _route_to_deadline_agent(text: str, group: str, category: str) -> str:
    """Feed deadline-relevant message to the deadline aggregator.

    TODO: Implement once real data flows. Will likely:
    1. Use LLM to extract due date + title from the message
    2. Upsert a Deadline row with source="groupchat"
    """
    logger.info("Would route to deadline agent: [%s] from %s", category, group)
    return "deadline_agent_placeholder"


async def _route_to_placement_agent(text: str, group: str) -> str:
    """Feed placement-relevant message to the placement prep agent.

    TODO: Implement once real data flows. Will likely:
    1. Use LLM to extract company, date, rounds from message
    2. Upsert a PlacementDrive row with source_email_id=None (groupchat source)
    """
    logger.info("Would route to placement agent: from %s", group)
    return "placement_agent_placeholder"


async def _route_to_notice_pipeline(text: str, group: str, category: str) -> str:
    """Feed announcement/event message to the existing notice pipeline.

    TODO: Implement once real data flows. Will create a Notice record
    matching the existing WhatsApp webhook handler pattern.
    """
    logger.info("Would route to notice pipeline: [%s] from %s", category, group)
    return "notice_pipeline_placeholder"

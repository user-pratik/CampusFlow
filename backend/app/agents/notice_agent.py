"""NoticeAgent — LLM-powered entity extraction from raw WhatsApp messages."""

from app.agents.base import BaseAgent
from app.schemas.extraction import NoticeExtraction
from app.utils.llm_client import chat_completion

SYSTEM_PROMPT = """\
You are a campus notice parser. Given raw text from a college WhatsApp group, \
extract structured information.

Rules:
- parsed_title: A concise title (max 12 words) summarizing the notice.
- category: One of "Urgent", "Event", "Academic", "General".
- is_actionable_task: True if the notice implies something a student must DO \
  (submit, attend, register, pay, etc.).
- deadline: The due date/time if is_actionable_task is True. Null otherwise. \
  Use ISO 8601 format (e.g., "2026-06-14T17:00:00").
- is_calendar_event: True if the notice describes a scheduled event with a time.
- start_time / end_time: Event timing if is_calendar_event is True. Null otherwise. \
  Use ISO 8601 format.
- location: Physical or virtual location if mentioned. Null otherwise.

Return ONLY valid JSON matching the schema. No commentary.\
"""


class NoticeAgent(BaseAgent):
    """Extracts structured notice data from raw text using an LLM."""

    async def execute(self, payload: dict) -> dict:
        """Parse raw WhatsApp text into a NoticeExtraction dict.

        Args:
            payload: Must contain 'raw_text' and 'source_group'.

        Returns:
            Dict with all NoticeExtraction fields plus the original
            'raw_text' and 'source_group' passed through.
        """
        raw_text = payload["raw_text"]
        source_group = payload["source_group"]

        content = await chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        extracted = NoticeExtraction.model_validate_json(content)

        return {
            "raw_text": raw_text,
            "source_group": source_group,
            **extracted.model_dump(mode="json"),
        }

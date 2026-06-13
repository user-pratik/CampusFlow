"""Pydantic schema enforcing structured output from the LLM extraction step."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class NoticeExtraction(BaseModel):
    """Schema for the structured data extracted from a raw notice by the LLM.

    This model is used as the `response_format` when calling the LLM,
    guaranteeing we always get a well-typed, validated result.
    """

    parsed_title: str
    category: Literal["Urgent", "Event", "Academic", "General"]
    is_actionable_task: bool
    deadline: datetime | None = None
    is_calendar_event: bool
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None

"""DigestAgent — Generates a personalized morning briefing using Groq LLM."""

import logging

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.base import BaseAgent
from app.database import async_session_maker
from app.models import Digest, Notice, Task
from app.utils.user_context import get_user_profile
from app.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "Unable to generate new briefing. Connection to intelligence core timed out."
)


class DigestAgent(BaseAgent):
    """Generates a personalized 3-bullet morning briefing and saves to DB."""

    async def execute(self, payload: dict) -> dict:
        """Generate and persist a morning digest.

        Args:
            payload: Currently unused, pass empty dict.

        Returns:
            Dict with 'digest_id', 'content', and 'generated_at'.
        """
        # 1. Gather context
        profile = get_user_profile()
        notices, tasks = await self._fetch_recent_data()

        # 2. Build prompt
        prompt = self._build_prompt(profile, notices, tasks)

        # 3. Call LLM with fallback
        content = await self._call_llm(prompt)

        # 4. Save to DB
        digest = await self._save_digest(content)

        return {
            "digest_id": digest.id,
            "content": digest.content,
            "generated_at": digest.generated_at.isoformat(),
        }

    async def _fetch_recent_data(self) -> tuple[list[Notice], list[Task]]:
        """Fetch the latest unprocessed notices and pending tasks (max 10 each)."""
        async with async_session_maker() as session:
            notices_result = await session.exec(
                select(Notice)
                .where(Notice.is_processed == False)
                .order_by(Notice.created_at.desc())
                .limit(10)
            )
            notices = list(notices_result.all())

            tasks_result = await session.exec(
                select(Task)
                .where(Task.status == "pending")
                .order_by(Task.deadline.asc())
                .limit(10)
            )
            tasks = list(tasks_result.all())

        return notices, tasks

    def _build_prompt(
        self, profile: dict, notices: list[Notice], tasks: list[Task]
    ) -> str:
        """Construct the LLM prompt with user context and recent data."""
        # Format notices
        notice_lines = "\n".join(
            f"- [{n.category}] {n.parsed_title} (from {n.source_group})"
            for n in notices
        ) or "No new notices."

        # Format tasks
        task_lines = "\n".join(
            f"- {t.title} (deadline: {t.deadline.strftime('%b %d, %I:%M %p')}"
            f"{', CONFLICT' if t.is_conflict else ''})"
            for t in tasks
        ) or "No pending tasks."

        return f"""\
USER PROFILE:
Name: {profile.get('name', 'Student')}
Branch: {profile.get('branch', 'Unknown')}
College: {profile.get('college', 'Unknown')}
Interests: {', '.join(profile.get('interests', []))}
Current Focus: {profile.get('current_focus', 'General studies')}

RECENT NOTICES:
{notice_lines}

PENDING TASKS:
{task_lines}

INSTRUCTIONS:
Read the user profile. Read the provided tasks and notices. Write a personalized \
3-bullet morning briefing addressed to the user by name. Relate the notices to their \
specific branch/interests if applicable. Max 150 words. Output plain text, no markdown headers."""

    async def _call_llm(self, prompt: str) -> str:
        """Call Groq LLM with timeout fallback and rolling key rotation."""
        try:
            content = await chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a concise campus assistant that writes brief, actionable morning summaries for college students.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=300,
                timeout=15.0,
            )
            if not content or not content.strip():
                return FALLBACK_MESSAGE
            return content.strip()
        except Exception as e:
            logger.warning("DigestAgent LLM call failed: %s", e)
            return FALLBACK_MESSAGE

    async def _save_digest(self, content: str) -> Digest:
        """Persist the generated digest to the database."""
        async with async_session_maker() as session:
            digest = Digest(content=content)
            session.add(digest)
            await session.commit()
            await session.refresh(digest)
        return digest

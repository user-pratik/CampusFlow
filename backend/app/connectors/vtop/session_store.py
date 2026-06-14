"""Database-backed VTOP session store.

Replaces file-based vtop_session.json with persistent DB storage.
Manages session lifecycle: save, retrieve, expire.
"""

import json
import logging
from datetime import datetime

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import async_session_maker
from app.models import VTOPSessionRecord

logger = logging.getLogger(__name__)


class SessionStore:
    """Manages VTOP session records in the database."""

    async def save_session(self, cookies: list[dict], csrf_token: str | None) -> None:
        """Invalidate any existing sessions and store a new one.

        Args:
            cookies: List of cookie dicts with keys: name, value, domain, path.
            csrf_token: The CSRF token extracted from the VTOP response, if any.
        """
        async with async_session_maker() as session:
            # Mark all existing valid sessions as invalid
            stmt = select(VTOPSessionRecord).where(VTOPSessionRecord.is_valid == True)
            result = await session.exec(stmt)
            for record in result.all():
                record.is_valid = False
                session.add(record)

            # Create new session record
            new_record = VTOPSessionRecord(
                cookies_json=json.dumps(cookies),
                csrf_token=csrf_token,
                established_at=datetime.utcnow(),
                is_valid=True,
            )
            session.add(new_record)
            await session.commit()
            logger.info("Saved new VTOP session (id=%s).", new_record.id)

    async def get_active_session(self) -> VTOPSessionRecord | None:
        """Return the most recent valid session, or None if none exists."""
        async with async_session_maker() as session:
            stmt = (
                select(VTOPSessionRecord)
                .where(VTOPSessionRecord.is_valid == True)
                .order_by(VTOPSessionRecord.established_at.desc())  # type: ignore[union-attr]
            )
            result = await session.exec(stmt)
            return result.first()

    async def mark_expired(self) -> None:
        """Set is_valid=False on the current active session."""
        async with async_session_maker() as session:
            stmt = select(VTOPSessionRecord).where(VTOPSessionRecord.is_valid == True)
            result = await session.exec(stmt)
            for record in result.all():
                record.is_valid = False
                session.add(record)
            await session.commit()
            logger.info("Marked active VTOP session(s) as expired.")

    async def get_cookies_as_httpx(self) -> httpx.Cookies | None:
        """Load cookies from the active session and return as httpx.Cookies.

        Returns None if no valid session exists.
        """
        record = await self.get_active_session()
        if record is None:
            return None

        cookies = httpx.Cookies()
        cookie_list: list[dict] = json.loads(record.cookies_json)
        for cookie in cookie_list:
            cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )
        return cookies

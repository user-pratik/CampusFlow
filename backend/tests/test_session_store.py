"""Tests for VTOP SessionStore and VTOPSessionRecord model.

Validates Requirements 3.1, 3.2, 3.7:
- Cookie capture and storage
- Timestamp recording on session establishment
- JSESSIONID-based session identification (store layer)
"""

import json
from datetime import datetime
from unittest.mock import patch

import httpx
import pytest
from sqlmodel import select

from app.connectors.vtop.session_store import SessionStore
from app.models import VTOPSessionRecord


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def session_store(test_engine):
    """SessionStore wired to the in-memory test database."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    test_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    # Patch the module-level async_session_maker used by SessionStore
    with patch(
        "app.connectors.vtop.session_store.async_session_maker", test_session_maker
    ):
        yield SessionStore()


@pytest.fixture
def sample_cookies() -> list[dict]:
    return [
        {
            "name": "JSESSIONID",
            "value": "ABC123DEF456",
            "domain": "vtopcc.vit.ac.in",
            "path": "/vtop",
        },
        {
            "name": "other_cookie",
            "value": "xyz789",
            "domain": "vtopcc.vit.ac.in",
            "path": "/",
        },
    ]


# ─── Unit Tests: save_session ─────────────────────────────────────────────────


async def test_save_session_stores_cookies(session_store, sample_cookies):
    """save_session persists cookies as JSON in the DB."""
    await session_store.save_session(sample_cookies, csrf_token="tok123")

    record = await session_store.get_active_session()
    assert record is not None
    stored_cookies = json.loads(record.cookies_json)
    assert stored_cookies == sample_cookies


async def test_save_session_stores_csrf_token(session_store, sample_cookies):
    """save_session persists the CSRF token."""
    await session_store.save_session(sample_cookies, csrf_token="my_csrf")

    record = await session_store.get_active_session()
    assert record is not None
    assert record.csrf_token == "my_csrf"


async def test_save_session_stores_none_csrf(session_store, sample_cookies):
    """save_session handles None csrf_token."""
    await session_store.save_session(sample_cookies, csrf_token=None)

    record = await session_store.get_active_session()
    assert record is not None
    assert record.csrf_token is None


async def test_save_session_records_timestamp(session_store, sample_cookies):
    """save_session records a UTC established_at timestamp."""
    before = datetime.utcnow()
    await session_store.save_session(sample_cookies, csrf_token=None)
    after = datetime.utcnow()

    record = await session_store.get_active_session()
    assert record is not None
    assert before <= record.established_at <= after


async def test_save_session_invalidates_previous(session_store, sample_cookies):
    """save_session marks prior valid sessions as invalid."""
    await session_store.save_session(sample_cookies, csrf_token="first")
    await session_store.save_session(sample_cookies, csrf_token="second")

    # Only the latest session should be active
    record = await session_store.get_active_session()
    assert record is not None
    assert record.csrf_token == "second"


# ─── Unit Tests: get_active_session ───────────────────────────────────────────


async def test_get_active_session_returns_none_when_empty(session_store):
    """get_active_session returns None with no stored sessions."""
    result = await session_store.get_active_session()
    assert result is None


async def test_get_active_session_returns_valid_only(session_store, sample_cookies):
    """get_active_session only returns sessions where is_valid=True."""
    await session_store.save_session(sample_cookies, csrf_token="tok")
    await session_store.mark_expired()

    result = await session_store.get_active_session()
    assert result is None


# ─── Unit Tests: mark_expired ─────────────────────────────────────────────────


async def test_mark_expired_invalidates_session(session_store, sample_cookies):
    """mark_expired sets is_valid=False on the active session."""
    await session_store.save_session(sample_cookies, csrf_token="tok")
    await session_store.mark_expired()

    result = await session_store.get_active_session()
    assert result is None


async def test_mark_expired_no_op_when_none(session_store):
    """mark_expired does not raise when no active session exists."""
    # Should not throw
    await session_store.mark_expired()


# ─── Unit Tests: get_cookies_as_httpx ─────────────────────────────────────────


async def test_get_cookies_as_httpx_returns_cookies(session_store, sample_cookies):
    """get_cookies_as_httpx returns httpx.Cookies with stored values."""
    await session_store.save_session(sample_cookies, csrf_token=None)

    cookies = await session_store.get_cookies_as_httpx()
    assert cookies is not None
    assert isinstance(cookies, httpx.Cookies)
    assert cookies.get("JSESSIONID", domain="vtopcc.vit.ac.in", path="/vtop") == "ABC123DEF456"
    assert cookies.get("other_cookie", domain="vtopcc.vit.ac.in", path="/") == "xyz789"


async def test_get_cookies_as_httpx_returns_none_no_session(session_store):
    """get_cookies_as_httpx returns None when no valid session exists."""
    result = await session_store.get_cookies_as_httpx()
    assert result is None


async def test_get_cookies_as_httpx_returns_none_after_expire(session_store, sample_cookies):
    """get_cookies_as_httpx returns None after session is expired."""
    await session_store.save_session(sample_cookies, csrf_token=None)
    await session_store.mark_expired()

    result = await session_store.get_cookies_as_httpx()
    assert result is None

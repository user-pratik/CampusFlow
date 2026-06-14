"""Unit tests for VTOP SessionValidator.

Tests session validation logic by mocking httpx responses and the SessionStore.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from app.connectors.vtop.session_validator import SessionValidator, SessionStatus


@pytest.fixture
def mock_session_store():
    """Create a mock SessionStore with controllable behavior."""
    store = AsyncMock()
    store.get_active_session = AsyncMock()
    store.get_cookies_as_httpx = AsyncMock()
    store.mark_expired = AsyncMock()
    return store


@pytest.fixture
def mock_session_record():
    """Create a mock VTOPSessionRecord."""
    record = MagicMock()
    record.established_at = datetime(2024, 1, 15, 10, 30, 0)
    record.is_valid = True
    return record


class TestSessionValidatorNoSession:
    """Tests when no active session exists."""

    async def test_returns_no_session_when_no_active_record(self, mock_session_store):
        mock_session_store.get_active_session.return_value = None
        validator = SessionValidator(session_store=mock_session_store)

        result = await validator.validate()

        assert result.status == "no_session"
        assert result.error is None

    async def test_returns_no_session_when_cookies_are_none(
        self, mock_session_store, mock_session_record
    ):
        mock_session_store.get_active_session.return_value = mock_session_record
        mock_session_store.get_cookies_as_httpx.return_value = None
        validator = SessionValidator(session_store=mock_session_store)

        result = await validator.validate()

        assert result.status == "no_session"


class TestSessionValidatorValid:
    """Tests when session cookies are valid (no redirect to login)."""

    async def test_returns_valid_when_response_stays_on_content(
        self, mock_session_store, mock_session_record
    ):
        mock_session_store.get_active_session.return_value = mock_session_record
        mock_session_store.get_cookies_as_httpx.return_value = httpx.Cookies()

        mock_response = MagicMock()
        mock_response.url = httpx.URL("https://vtopcc.vit.ac.in/vtop/content")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            validator = SessionValidator(session_store=mock_session_store)
            result = await validator.validate()

        assert result.status == "valid"
        assert result.established_at == "2024-01-15T10:30:00"
        assert result.error is None

    async def test_valid_does_not_mark_expired(
        self, mock_session_store, mock_session_record
    ):
        mock_session_store.get_active_session.return_value = mock_session_record
        mock_session_store.get_cookies_as_httpx.return_value = httpx.Cookies()

        mock_response = MagicMock()
        mock_response.url = httpx.URL("https://vtopcc.vit.ac.in/vtop/content")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            validator = SessionValidator(session_store=mock_session_store)
            await validator.validate()

        mock_session_store.mark_expired.assert_not_called()


class TestSessionValidatorExpired:
    """Tests when session has expired (redirects to login)."""

    async def test_returns_session_expired_on_login_redirect(
        self, mock_session_store, mock_session_record
    ):
        mock_session_store.get_active_session.return_value = mock_session_record
        mock_session_store.get_cookies_as_httpx.return_value = httpx.Cookies()

        mock_response = MagicMock()
        mock_response.url = httpx.URL("https://vtopcc.vit.ac.in/vtop/login")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            validator = SessionValidator(session_store=mock_session_store)
            result = await validator.validate()

        assert result.status == "session_expired"
        assert result.established_at == "2024-01-15T10:30:00"

    async def test_marks_session_expired_in_store(
        self, mock_session_store, mock_session_record
    ):
        mock_session_store.get_active_session.return_value = mock_session_record
        mock_session_store.get_cookies_as_httpx.return_value = httpx.Cookies()

        mock_response = MagicMock()
        mock_response.url = httpx.URL("https://vtopcc.vit.ac.in/vtop/login?something")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            validator = SessionValidator(session_store=mock_session_store)
            await validator.validate()

        mock_session_store.mark_expired.assert_called_once()


class TestSessionValidatorNetworkErrors:
    """Tests when network errors or timeouts occur."""

    async def test_returns_validation_failed_on_timeout(
        self, mock_session_store, mock_session_record
    ):
        mock_session_store.get_active_session.return_value = mock_session_record
        mock_session_store.get_cookies_as_httpx.return_value = httpx.Cookies()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            validator = SessionValidator(session_store=mock_session_store)
            result = await validator.validate()

        assert result.status == "validation_failed"
        assert "timed out" in result.error

    async def test_returns_validation_failed_on_connection_error(
        self, mock_session_store, mock_session_record
    ):
        mock_session_store.get_active_session.return_value = mock_session_record
        mock_session_store.get_cookies_as_httpx.return_value = httpx.Cookies()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            validator = SessionValidator(session_store=mock_session_store)
            result = await validator.validate()

        assert result.status == "validation_failed"
        assert "ConnectError" in result.error

    async def test_returns_validation_failed_on_generic_http_error(
        self, mock_session_store, mock_session_record
    ):
        mock_session_store.get_active_session.return_value = mock_session_record
        mock_session_store.get_cookies_as_httpx.return_value = httpx.Cookies()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.NetworkError("network issue")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            validator = SessionValidator(session_store=mock_session_store)
            result = await validator.validate()

        assert result.status == "validation_failed"
        assert "NetworkError" in result.error

"""Unit tests for CookieInterceptor."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.connectors.vtop.cookie_interceptor import CookieInterceptor, CaptureResult


@pytest.fixture
def interceptor():
    return CookieInterceptor()


class TestDetectLoginSuccess:
    """Tests for detect_login_success method."""

    def test_redirected_away_from_login(self, interceptor):
        """Response URL not containing /vtop/login means success."""
        assert interceptor.detect_login_success(
            "https://vtopcc.vit.ac.in/vtop/content", "login"
        ) is True

    def test_still_on_login_page(self, interceptor):
        """Response URL still on /vtop/login means failure."""
        assert interceptor.detect_login_success(
            "https://vtopcc.vit.ac.in/vtop/login", "login"
        ) is False

    def test_login_in_query_params(self, interceptor):
        """URL with /vtop/login anywhere in path is considered login page."""
        assert interceptor.detect_login_success(
            "https://vtopcc.vit.ac.in/vtop/login?error=invalid", "login"
        ) is False

    def test_different_vtop_page(self, interceptor):
        """Any non-login VTOP page is a login success."""
        assert interceptor.detect_login_success(
            "https://vtopcc.vit.ac.in/vtop/academics", "login"
        ) is True


class TestExtractCookies:
    """Tests for extract_cookies method."""

    def test_single_cookie(self, interceptor):
        headers = ["JSESSIONID=ABC123; Path=/vtop; Domain=vtopcc.vit.ac.in"]
        result = interceptor.extract_cookies(headers)
        assert len(result) == 1
        assert result[0]["name"] == "JSESSIONID"
        assert result[0]["value"] == "ABC123"
        assert result[0]["path"] == "/vtop"
        assert result[0]["domain"] == "vtopcc.vit.ac.in"

    def test_multiple_cookies(self, interceptor):
        headers = [
            "JSESSIONID=ABC123; Path=/vtop; Domain=vtopcc.vit.ac.in",
            "other_cookie=value456; Path=/; Domain=vtopcc.vit.ac.in",
        ]
        result = interceptor.extract_cookies(headers)
        assert len(result) == 2
        names = {c["name"] for c in result}
        assert "JSESSIONID" in names
        assert "other_cookie" in names

    def test_empty_headers(self, interceptor):
        result = interceptor.extract_cookies([])
        assert result == []

    def test_cookie_with_no_domain(self, interceptor):
        headers = ["JSESSIONID=ABC123; Path=/vtop"]
        result = interceptor.extract_cookies(headers)
        assert len(result) == 1
        assert result[0]["domain"] == ""

    def test_cookie_with_no_path(self, interceptor):
        headers = ["JSESSIONID=ABC123; Domain=vtopcc.vit.ac.in"]
        result = interceptor.extract_cookies(headers)
        assert len(result) == 1
        # SimpleCookie defaults path to empty string if not specified
        assert result[0]["path"] in ("", "/")


class TestValidateCookies:
    """Tests for validate_cookies method."""

    def test_valid_with_jsessionid(self, interceptor):
        cookies = [
            {"name": "JSESSIONID", "value": "ABC", "domain": "", "path": "/"},
            {"name": "other", "value": "xyz", "domain": "", "path": "/"},
        ]
        assert interceptor.validate_cookies(cookies) is True

    def test_invalid_without_jsessionid(self, interceptor):
        cookies = [
            {"name": "other", "value": "xyz", "domain": "", "path": "/"},
        ]
        assert interceptor.validate_cookies(cookies) is False

    def test_empty_cookies(self, interceptor):
        assert interceptor.validate_cookies([]) is False

    def test_case_sensitive_jsessionid(self, interceptor):
        """JSESSIONID check is case-sensitive per spec."""
        cookies = [
            {"name": "jsessionid", "value": "abc", "domain": "", "path": "/"},
        ]
        assert interceptor.validate_cookies(cookies) is False


class TestCaptureAndStore:
    """Tests for capture_and_store async pipeline."""

    @pytest.mark.asyncio
    async def test_successful_capture(self, interceptor):
        """Full successful pipeline: redirect + valid cookies → stored."""
        response = MagicMock()
        response.url = "https://vtopcc.vit.ac.in/vtop/content"
        response.headers = MagicMock()
        response.headers.get_list = MagicMock(
            return_value=["JSESSIONID=ABC123; Path=/vtop; Domain=vtopcc.vit.ac.in"]
        )

        session_store = AsyncMock()
        session_store.save_session = AsyncMock()

        result = await interceptor.capture_and_store(response, session_store)

        assert result.success is True
        assert result.status == "login_success"
        session_store.save_session.assert_called_once()
        call_kwargs = session_store.save_session.call_args
        assert call_kwargs[1]["cookies"][0]["name"] == "JSESSIONID"

    @pytest.mark.asyncio
    async def test_login_failed_still_on_login_page(self, interceptor):
        """Still on login page → login_failed."""
        response = MagicMock()
        response.url = "https://vtopcc.vit.ac.in/vtop/login"

        session_store = AsyncMock()
        result = await interceptor.capture_and_store(response, session_store)

        assert result.success is False
        assert result.status == "login_failed"
        session_store.save_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_set_cookie_headers(self, interceptor):
        """Redirect but no Set-Cookie headers → login_failed."""
        response = MagicMock()
        response.url = "https://vtopcc.vit.ac.in/vtop/content"
        response.headers = MagicMock()
        response.headers.get_list = MagicMock(return_value=[])

        session_store = AsyncMock()
        result = await interceptor.capture_and_store(response, session_store)

        assert result.success is False
        assert result.status == "login_failed"
        session_store.save_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_jsessionid(self, interceptor):
        """Redirect + cookies but no JSESSIONID → invalid_cookies."""
        response = MagicMock()
        response.url = "https://vtopcc.vit.ac.in/vtop/content"
        response.headers = MagicMock()
        response.headers.get_list = MagicMock(
            return_value=["other_cookie=val; Path=/; Domain=vtopcc.vit.ac.in"]
        )

        session_store = AsyncMock()
        result = await interceptor.capture_and_store(response, session_store)

        assert result.success is False
        assert result.status == "invalid_cookies"
        session_store.save_session.assert_not_called()

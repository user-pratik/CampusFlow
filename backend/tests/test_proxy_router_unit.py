"""Integration-level unit tests for the VTOP proxy router endpoints.

Tests the proxy router endpoints (GET/POST /api/vtop/proxy/...) and the
full sync flow (session-status → semesters → sync) using the httpx
AsyncClient fixture with mocked upstream VTOP calls.

Validates Requirements: 1.1, 1.3, 1.5, 3.1, 4.3, 6.1, 6.4
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.connectors.vtop.session_validator import SessionStatus
from app.connectors.vtop.sync_orchestrator import SyncResult


# ─── HTML Fixtures ────────────────────────────────────────────────────────────

VTOP_LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://vtopcc.vit.ac.in/vtop/css/bootstrap.css">
    <script src="https://vtopcc.vit.ac.in/vtop/js/jquery.min.js"></script>
</head>
<body>
<h1>VTOP Login</h1>
<form action="https://vtopcc.vit.ac.in/vtop/doLogin" method="post">
    <input type="text" name="uname" />
    <input type="password" name="passwd" />
    <button type="submit">Login</button>
</form>
</body>
</html>"""

VTOP_CONTENT_HTML = """<!DOCTYPE html>
<html>
<head><meta name="_csrf" content="csrf-token-abc123"></head>
<body><h1>Welcome to VTOP</h1></body>
</html>"""


def _make_httpx_response(
    status_code: int = 200,
    content: bytes = b"OK",
    headers: dict | None = None,
    url: str = "https://vtopcc.vit.ac.in/vtop/login",
    charset_encoding: str = "utf-8",
) -> MagicMock:
    """Create a mock httpx.Response with required attributes."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = httpx.Headers(headers or {"content-type": "text/html; charset=utf-8"})
    resp.url = url
    resp.charset_encoding = charset_encoding
    return resp


# ─── Test: GET /api/vtop/proxy/login returns stripped headers (Req 1.1) ───────


class TestProxyGetStrippedHeaders:
    """GET /api/vtop/proxy/login should strip frame-blocking headers."""

    @pytest.mark.asyncio
    async def test_strips_x_frame_options(self, client):
        """X-Frame-Options is removed from the proxied response."""
        upstream_resp = _make_httpx_response(
            content=b"<html><body>Login</body></html>",
            headers={
                "content-type": "text/html",
                "x-frame-options": "DENY",
                "server": "nginx",
            },
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.get("/api/vtop/proxy/login")

        assert response.status_code == 200
        assert "x-frame-options" not in response.headers
        assert "X-Frame-Options" not in response.headers

    @pytest.mark.asyncio
    async def test_strips_content_security_policy(self, client):
        """Content-Security-Policy is removed from the proxied response."""
        upstream_resp = _make_httpx_response(
            content=b"<html><body>Login</body></html>",
            headers={
                "content-type": "text/html",
                "content-security-policy": "frame-ancestors 'none'",
            },
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.get("/api/vtop/proxy/login")

        assert response.status_code == 200
        assert "content-security-policy" not in response.headers


# ─── Test: POST /api/vtop/proxy/login triggers cookie capture (Req 3.1) ──────


class TestProxyPostLoginCookieCapture:
    """POST /api/vtop/proxy/login should trigger cookie capture on success."""

    @pytest.mark.asyncio
    async def test_login_post_calls_cookie_interceptor(self, client):
        """Successful login POST triggers CookieInterceptor.capture_and_store."""
        upstream_resp = _make_httpx_response(
            status_code=200,
            content=b"<html><body>Welcome to VTOP</body></html>",
            headers={
                "content-type": "text/html",
                "set-cookie": "JSESSIONID=ABC123; Path=/vtop; Domain=vtopcc.vit.ac.in",
            },
            url="https://vtopcc.vit.ac.in/vtop/content",
        )
        # Give it a get_list method for the cookie interceptor
        upstream_resp.headers = MagicMock()
        upstream_resp.headers.get = MagicMock(return_value="text/html")
        upstream_resp.headers.get_list = MagicMock(
            return_value=["JSESSIONID=ABC123; Path=/vtop; Domain=vtopcc.vit.ac.in"]
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with patch(
                "app.routers.vtop_proxy.CookieInterceptor.capture_and_store",
                new_callable=AsyncMock,
            ) as mock_capture:
                from app.connectors.vtop.cookie_interceptor import CaptureResult

                mock_capture.return_value = CaptureResult(
                    success=True, status="login_success"
                )

                response = await client.post(
                    "/api/vtop/proxy/login",
                    content=b"uname=testuser&passwd=testpass",
                )

        assert response.status_code == 200
        mock_capture.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_login_post_skips_cookie_capture(self, client):
        """POST to a non-login path does NOT trigger cookie capture."""
        upstream_resp = _make_httpx_response(
            content=b"<html><body>Some VTOP page</body></html>",
            headers={"content-type": "text/html"},
            url="https://vtopcc.vit.ac.in/vtop/academics",
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with patch(
                "app.routers.vtop_proxy.CookieInterceptor.capture_and_store",
                new_callable=AsyncMock,
            ) as mock_capture:
                response = await client.post(
                    "/api/vtop/proxy/academics/getData",
                    content=b"_csrf=token123",
                )

        assert response.status_code == 200
        mock_capture.assert_not_called()


# ─── Test: Proxy returns 502 on upstream timeout (Req 1.5) ────────────────────


class TestProxyTimeoutHandling:
    """Proxy should return 502 when upstream times out."""

    @pytest.mark.asyncio
    async def test_get_returns_502_on_timeout(self, client):
        """GET proxy returns 502 with error message on upstream timeout."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.TimeoutException("connection timed out")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.get("/api/vtop/proxy/login")

        assert response.status_code == 502
        data = response.json()
        assert "error" in data
        assert "timed out" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_post_returns_502_on_timeout(self, client):
        """POST proxy returns 502 with error message on upstream timeout."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("connection timed out")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.post(
                "/api/vtop/proxy/doLogin", content=b"data=test"
            )

        assert response.status_code == 502
        data = response.json()
        assert "timed out" in data["error"].lower()


# ─── Test: Proxy returns 502 on upstream 5xx (Req 1.5) ───────────────────────


class TestProxy5xxHandling:
    """Proxy should return 502 when upstream returns 5xx status."""

    @pytest.mark.asyncio
    async def test_get_returns_502_on_upstream_500(self, client):
        """GET proxy returns 502 when upstream responds with 500."""
        upstream_resp = _make_httpx_response(
            status_code=500,
            content=b"Internal Server Error",
            headers={"content-type": "text/plain"},
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.get("/api/vtop/proxy/login")

        assert response.status_code == 502
        data = response.json()
        assert "error" in data
        assert "500" in data["error"]

    @pytest.mark.asyncio
    async def test_get_returns_502_on_upstream_503(self, client):
        """GET proxy returns 502 when upstream responds with 503."""
        upstream_resp = _make_httpx_response(
            status_code=503,
            content=b"Service Unavailable",
            headers={"content-type": "text/plain"},
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.get("/api/vtop/proxy/some-page")

        assert response.status_code == 502
        data = response.json()
        assert "503" in data["error"]

    @pytest.mark.asyncio
    async def test_post_returns_502_on_upstream_5xx(self, client):
        """POST proxy returns 502 when upstream responds with 5xx."""
        upstream_resp = _make_httpx_response(
            status_code=502,
            content=b"Bad Gateway",
            headers={"content-type": "text/plain"},
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.post(
                "/api/vtop/proxy/doLogin", content=b"data=test"
            )

        assert response.status_code == 502
        data = response.json()
        assert "502" in data["error"]


# ─── Test: URL rewriting in HTML response content (Req 1.3) ──────────────────


class TestProxyUrlRewriting:
    """Proxy should rewrite VTOP URLs in HTML/JS responses."""

    @pytest.mark.asyncio
    async def test_rewrites_vtop_urls_in_html(self, client):
        """HTML responses have VTOP domain URLs rewritten to proxy paths."""
        upstream_resp = _make_httpx_response(
            content=VTOP_LOGIN_HTML.encode("utf-8"),
            headers={"content-type": "text/html; charset=utf-8"},
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.get("/api/vtop/proxy/login")

        body = response.text
        # All vtopcc.vit.ac.in URLs should be rewritten
        assert "vtopcc.vit.ac.in" not in body
        # Should contain proxy-based URLs
        assert "/api/vtop/proxy/css/bootstrap.css" in body
        assert "/api/vtop/proxy/js/jquery.min.js" in body
        assert "/api/vtop/proxy/doLogin" in body

    @pytest.mark.asyncio
    async def test_does_not_rewrite_non_html(self, client):
        """Non-HTML content types (e.g., images) are not rewritten."""
        image_content = b"\x89PNG\r\n\x1a\n"  # PNG header bytes
        upstream_resp = _make_httpx_response(
            content=image_content,
            headers={"content-type": "image/png"},
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.get("/api/vtop/proxy/images/logo.png")

        # Binary content should pass through unchanged
        assert response.content == image_content

    @pytest.mark.asyncio
    async def test_rewrites_javascript_content(self, client):
        """JavaScript responses have VTOP URLs rewritten."""
        js_content = b"var apiUrl = 'https://vtopcc.vit.ac.in/vtop/ajax/getData';"
        upstream_resp = _make_httpx_response(
            content=js_content,
            headers={"content-type": "application/javascript"},
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=upstream_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.get("/api/vtop/proxy/js/app.js")

        body = response.text
        assert "vtopcc.vit.ac.in" not in body
        assert "/api/vtop/proxy/ajax/getData" in body


# ─── Test: Full sync flow integration (Req 4.3, 6.1, 6.4) ───────────────────


class TestFullSyncFlowIntegration:
    """Test the full sync flow: session-status → semesters → sync."""

    @pytest.mark.asyncio
    async def test_full_sync_flow_valid_session(self, client):
        """Full flow: session valid → fetch semesters → trigger sync → success."""
        # Step 1: Check session status — valid
        mock_session_status = SessionStatus(
            status="valid", established_at="2024-06-15T10:30:00"
        )

        # Step 2: Fetch semesters
        mock_semesters = {"Fall 2024-25": "AP2024251"}

        # Step 3: Trigger sync
        mock_sync_result = SyncResult(
            status="completed",
            attendance_count=5,
            marks_count=10,
            profile_updated=True,
        )

        # Session status check
        with patch(
            "app.connectors.vtop.session_validator.SessionValidator.validate",
            new_callable=AsyncMock,
            return_value=mock_session_status,
        ):
            status_resp = await client.get("/api/vtop/session-status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "valid"

        # Semesters fetch
        with (
            patch(
                "app.connectors.vtop.sync_orchestrator.SyncOrchestrator.get_semesters",
                new_callable=AsyncMock,
                return_value=mock_semesters,
            ),
            patch(
                "app.connectors.vtop.sync_orchestrator.SyncOrchestrator.close",
                new_callable=AsyncMock,
            ),
        ):
            sem_resp = await client.get("/api/vtop/semesters")
        assert sem_resp.status_code == 200
        assert sem_resp.json()["semesters"] == mock_semesters

        # Sync trigger
        with (
            patch(
                "app.connectors.vtop.sync_orchestrator.SyncOrchestrator.sync_all",
                new_callable=AsyncMock,
                return_value=mock_sync_result,
            ),
            patch(
                "app.connectors.vtop.sync_orchestrator.SyncOrchestrator.close",
                new_callable=AsyncMock,
            ),
        ):
            sync_resp = await client.post(
                "/api/vtop/sync", json={"semester_id": "AP2024251"}
            )
        assert sync_resp.status_code == 200
        data = sync_resp.json()
        assert data["status"] == "completed"
        assert data["attendance_count"] == 5
        assert data["marks_count"] == 10
        assert data["profile_updated"] is True

    @pytest.mark.asyncio
    async def test_sync_flow_expired_session_triggers_relogin(self, client):
        """Flow with expired session: session-status returns expired, sync aborts."""
        mock_session_status = SessionStatus(
            status="session_expired", established_at="2024-06-15T10:30:00"
        )

        with patch(
            "app.connectors.vtop.session_validator.SessionValidator.validate",
            new_callable=AsyncMock,
            return_value=mock_session_status,
        ):
            status_resp = await client.get("/api/vtop/session-status")

        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "session_expired"
        # Frontend would open Login_Modal at this point

    @pytest.mark.asyncio
    async def test_sync_flow_session_expires_during_sync(self, client):
        """Session expires mid-sync: orchestrator aborts and returns session_expired."""
        mock_sync_result = SyncResult(
            status="session_expired",
            error="Session expired while scraping attendance.",
        )

        with (
            patch(
                "app.connectors.vtop.sync_orchestrator.SyncOrchestrator.sync_all",
                new_callable=AsyncMock,
                return_value=mock_sync_result,
            ),
            patch(
                "app.connectors.vtop.sync_orchestrator.SyncOrchestrator.close",
                new_callable=AsyncMock,
            ),
        ):
            sync_resp = await client.post(
                "/api/vtop/sync", json={"semester_id": "AP2024251"}
            )

        assert sync_resp.status_code == 200
        data = sync_resp.json()
        assert data["status"] == "session_expired"
        assert data["attendance_count"] == 0
        assert data["marks_count"] == 0
        assert "session expired" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_sync_flow_no_session(self, client):
        """No session: status returns no_session, frontend opens Login_Modal."""
        mock_session_status = SessionStatus(status="no_session")

        with patch(
            "app.connectors.vtop.session_validator.SessionValidator.validate",
            new_callable=AsyncMock,
            return_value=mock_session_status,
        ):
            status_resp = await client.get("/api/vtop/session-status")

        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "no_session"
        assert data["error"] is None
        assert data["established_at"] is None


# ─── Test: Proxy handles httpx connection errors ──────────────────────────────


class TestProxyConnectionErrors:
    """Proxy should return 502 on various connection failures."""

    @pytest.mark.asyncio
    async def test_get_returns_502_on_connect_error(self, client):
        """GET proxy returns 502 when connection to VTOP is refused."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.get("/api/vtop/proxy/login")

        assert response.status_code == 502
        data = response.json()
        assert "error" in data
        assert "unreachable" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_post_returns_502_on_network_error(self, client):
        """POST proxy returns 502 when network error occurs."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.NetworkError("network down")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            response = await client.post(
                "/api/vtop/proxy/login", content=b"uname=test"
            )

        assert response.status_code == 502
        data = response.json()
        assert "error" in data

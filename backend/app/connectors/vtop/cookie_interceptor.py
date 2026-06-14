"""Cookie Interceptor for VTOP proxy login flow.

Detects successful login via redirect analysis, extracts session cookies
from Set-Cookie headers, validates them, and stores via SessionStore.
"""

import logging
from http.cookies import SimpleCookie
from typing import Literal

from pydantic import BaseModel

from app.connectors.vtop.session_store import SessionStore

logger = logging.getLogger(__name__)


class CaptureResult(BaseModel):
    """Result of the cookie capture pipeline."""

    success: bool
    status: Literal["login_success", "login_failed", "invalid_cookies"]


class CookieInterceptor:
    """Intercepts VTOP proxy responses to capture session cookies on login."""

    def detect_login_success(self, response_url: str, original_path: str) -> bool:
        """Check if the response redirected away from /vtop/login.

        A successful login is indicated by the response URL no longer
        containing the login path. If we're still on the login page,
        the login failed (wrong credentials, bad captcha, etc.).

        Args:
            response_url: The final URL after any redirects.
            original_path: The original request path (e.g. "login").

        Returns:
            True if the response redirected away from /vtop/login.
        """
        return "/vtop/login" not in response_url

    def extract_cookies(self, set_cookie_headers: list[str]) -> list[dict]:
        """Parse Set-Cookie headers into structured cookie dicts.

        Each returned dict contains: name, value, domain, path.

        Args:
            set_cookie_headers: Raw Set-Cookie header values.

        Returns:
            List of cookie dicts with keys: name, value, domain, path.
        """
        cookies: list[dict] = []

        for header in set_cookie_headers:
            simple_cookie: SimpleCookie = SimpleCookie()
            try:
                simple_cookie.load(header)
            except Exception:
                logger.warning("Failed to parse Set-Cookie header: %s", header[:80])
                continue

            for name, morsel in simple_cookie.items():
                cookie_dict = {
                    "name": name,
                    "value": morsel.value,
                    "domain": morsel.get("domain", ""),
                    "path": morsel.get("path", "/"),
                }
                cookies.append(cookie_dict)

        return cookies

    def validate_cookies(self, cookies: list[dict]) -> bool:
        """Ensure at least one JSESSIONID cookie exists in the cookie set.

        Args:
            cookies: List of cookie dicts (from extract_cookies).

        Returns:
            True if at least one cookie has name == "JSESSIONID".
        """
        return any(cookie.get("name") == "JSESSIONID" for cookie in cookies)

    async def capture_and_store(
        self, response, session_store: SessionStore
    ) -> CaptureResult:
        """Full cookie capture pipeline: detect → extract → validate → store.

        This is the main entry point called by the proxy router after
        forwarding a POST to /vtop/login.

        Args:
            response: The httpx response object from the upstream request.
            session_store: SessionStore instance for persisting cookies.

        Returns:
            CaptureResult indicating success/failure and status.
        """
        # Step 1: Detect if login was successful (redirected away from login)
        response_url = str(response.url)
        if not self.detect_login_success(response_url, "login"):
            logger.info("Login not successful — still on login page.")
            return CaptureResult(success=False, status="login_failed")

        # Step 2: Extract cookies from Set-Cookie headers
        set_cookie_headers = response.headers.get_list("set-cookie")
        if not set_cookie_headers:
            logger.warning("Login redirect detected but no Set-Cookie headers found.")
            return CaptureResult(success=False, status="login_failed")

        cookies = self.extract_cookies(set_cookie_headers)
        if not cookies:
            logger.warning("Could not parse any cookies from Set-Cookie headers.")
            return CaptureResult(success=False, status="login_failed")

        # Step 3: Validate cookies (must contain JSESSIONID)
        if not self.validate_cookies(cookies):
            logger.warning("Cookie set missing required JSESSIONID cookie.")
            return CaptureResult(success=False, status="invalid_cookies")

        # Step 4: Store cookies in the session store
        await session_store.save_session(cookies=cookies, csrf_token=None)
        logger.info("Successfully captured and stored %d cookies.", len(cookies))

        return CaptureResult(success=True, status="login_success")

"""VTOP session manager — uses browser-saved cookies for authenticated requests.

Login flow:
1. User runs `python vtop_login_browser.py` once (solves reCAPTCHA in real browser)
2. Session cookies saved to vtop_session.json
3. This module loads those cookies and uses them for httpx requests
4. If session expires (302 to login), user must re-run the browser login
"""

import json
import logging
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://vtopcc.vit.ac.in/vtop"
SESSION_FILE = Path(__file__).resolve().parent.parent.parent.parent / "vtop_session.json"


class VTOPSession:
    """Manages an authenticated VTOP session using browser-saved cookies."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=False,
        )
        self._csrf: str = ""
        self._authenticated = False

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    async def login(self) -> bool:
        """Load session cookies from vtop_session.json (saved by browser login script).

        Returns True if cookies are loaded and session is still valid.
        """
        if not SESSION_FILE.exists():
            logger.error(
                "No VTOP session file found at %s. "
                "Run 'python vtop_login_browser.py' to authenticate via browser.",
                SESSION_FILE,
            )
            return False

        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            cookies = session_data.get("cookies", [])
            if not cookies:
                logger.error("Session file has no cookies.")
                return False

            # Load cookies into httpx client
            for cookie in cookies:
                self.client.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain", "vtopcc.vit.ac.in"),
                    path=cookie.get("path", "/"),
                )

            logger.info("Loaded %d cookies from session file.", len(cookies))

            # Verify session is still valid by hitting the student home
            test_resp = await self.client.get(f"{BASE_URL}/content")
            if "/login" in str(test_resp.url):
                logger.error(
                    "Session expired. Re-run 'python vtop_login_browser.py' to re-authenticate."
                )
                return False

            # Extract CSRF from the page
            soup = BeautifulSoup(test_resp.text, "lxml")
            self._csrf = self._extract_csrf(soup)

            self._authenticated = True
            logger.info("VTOP session is valid and active.")
            return True

        except Exception as e:
            logger.error("Failed to load VTOP session: %s", e)
            return False

    async def post_page(self, path: str, extra_data: dict | None = None) -> BeautifulSoup | None:
        """POST to an authenticated VTOP page."""
        if not self._authenticated:
            logger.warning("Not authenticated — run vtop_login_browser.py first.")
            return None

        url = path if path.startswith("http") else f"https://vtopcc.vit.ac.in{path}"
        data = {"_csrf": self._csrf, **(extra_data or {})}

        try:
            resp = await self.client.post(url, data=data)

            if "/login" in str(resp.url):
                logger.warning("Session expired mid-request.")
                self._authenticated = False
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            new_csrf = self._extract_csrf(soup)
            if new_csrf:
                self._csrf = new_csrf

            return soup
        except Exception as e:
            logger.error("POST to %s failed: %s", path, e)
            return None

    async def close(self):
        await self.client.aclose()

    def _extract_csrf(self, soup: BeautifulSoup) -> str:
        tag = soup.find("input", {"name": "_csrf"})
        if tag and tag.get("value"):
            return tag["value"]
        meta = soup.find("meta", {"name": "_csrf"})
        if meta and meta.get("content"):
            return meta["content"]
        return self._csrf

"""Gmail API client for CampusFlow.

Handles OAuth2 authentication and email fetching.
"""

import base64
import logging
import re
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CREDENTIALS_FILE = BACKEND_ROOT / "credentials.json"
TOKEN_FILE = BACKEND_ROOT / "gmail_token.json"


def authenticate() -> Optional[Credentials]:
    """Authenticate with Gmail API using OAuth2."""
    creds = None

    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            logger.warning("Failed to load token: %s", e)
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if not CREDENTIALS_FILE.exists():
            logger.error("credentials.json not found at %s", CREDENTIALS_FILE)
            return None
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=8090, open_browser=True)
            TOKEN_FILE.write_text(creds.to_json())
        except Exception as e:
            logger.error("OAuth flow failed: %s", e)
            return None

    return creds


def get_service():
    """Get authenticated Gmail API service."""
    creds = authenticate()
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds)


def get_messages(max_results: int = 50, query: str = "") -> list[dict]:
    """Fetch message list from Gmail inbox."""
    service = get_service()
    if not service:
        return []
    try:
        results = service.users().messages().list(userId="me", maxResults=max_results, q=query).execute()
        return results.get("messages", [])
    except Exception as e:
        logger.error("Failed to fetch messages: %s", e)
        return []


def get_message_detail(msg_id: str) -> Optional[dict]:
    """Fetch full details of a single email."""
    service = get_service()
    if not service:
        return None
    try:
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        header_dict = {h["name"].lower(): h["value"] for h in headers}

        subject = header_dict.get("subject", "(No Subject)")
        sender = header_dict.get("from", "Unknown")
        date_str = header_dict.get("date", "")

        received_at = None
        if date_str:
            try:
                received_at = parsedate_to_datetime(date_str).isoformat()
            except Exception:
                received_at = date_str

        body_text = _extract_body(msg.get("payload", {}))

        return {
            "msg_id": msg_id,
            "subject": subject,
            "sender": sender,
            "date": received_at,
            "body_text": body_text[:5000],
        }
    except Exception as e:
        logger.error("Failed to fetch message %s: %s", msg_id, e)
        return None


def is_authenticated() -> bool:
    """Check if Gmail token exists and is valid."""
    if not TOKEN_FILE.exists():
        return False
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds.valid:
            return True
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
            return True
    except Exception:
        pass
    return False


def _extract_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    for part in parts:
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                text = re.sub(r"<[^>]+>", " ", html)
                text = re.sub(r"\s+", " ", text).strip()
                return text[:5000]

    for part in parts:
        result = _extract_body(part)
        if result:
            return result

    return ""

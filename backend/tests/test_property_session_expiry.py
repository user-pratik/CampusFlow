"""Property-based test for session expiry detection via redirect.

Feature: embedded-vtop-login, Property 6: Session expiry detection via redirect

Validates: Requirements 4.4
"""

from hypothesis import given, settings, assume
from hypothesis.strategies import text, composite, sampled_from
from unittest.mock import MagicMock, AsyncMock

from app.connectors.vtop.sync_orchestrator import SyncOrchestrator


# Create an orchestrator instance with a mocked session store
orchestrator = SyncOrchestrator(AsyncMock())


@composite
def url_with_login(draw):
    """Generate URLs that contain the VTOP login path."""
    prefix = draw(sampled_from(["https://vtopcc.vit.ac.in", "http://vtopcc.vit.ac.in"]))
    suffix = draw(text(alphabet="abcdefghijklmnop?=&", max_size=20))
    return f"{prefix}/vtop/login{suffix}"


@composite
def url_without_login(draw):
    """Generate URLs that do NOT contain the VTOP login path."""
    prefix = draw(sampled_from([
        "https://vtopcc.vit.ac.in/vtop/content",
        "https://vtopcc.vit.ac.in/vtop/academics/something",
    ]))
    suffix = draw(text(alphabet="abcdefghijklmnop/", max_size=20))
    url = f"{prefix}{suffix}"
    assume("/vtop/login" not in url)
    return url


@settings(max_examples=100)
@given(url=url_with_login())
def test_session_expired_detected_on_login_url(url):
    """For any HTTP response whose final URL contains the VTOP login path,
    _is_login_redirect SHALL return True (session expired).

    **Validates: Requirements 4.4**
    """
    mock_resp = MagicMock()
    mock_resp.url = url
    assert orchestrator._is_login_redirect(mock_resp) is True


@settings(max_examples=100)
@given(url=url_without_login())
def test_session_valid_on_non_login_url(url):
    """For any HTTP response whose final URL does NOT contain the VTOP login path,
    _is_login_redirect SHALL return False (session valid).

    **Validates: Requirements 4.4**
    """
    mock_resp = MagicMock()
    mock_resp.url = url
    assert orchestrator._is_login_redirect(mock_resp) is False

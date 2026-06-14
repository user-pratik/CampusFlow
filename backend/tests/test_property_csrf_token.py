"""Property-based test for CSRF token inclusion in all scraping requests.

Feature: embedded-vtop-login, Property 11: CSRF token inclusion in all scraping requests

Validates: Requirements 6.5
"""

import asyncio

from hypothesis import given, settings
from hypothesis.strategies import text
from unittest.mock import MagicMock, AsyncMock

from app.connectors.vtop.sync_orchestrator import SyncOrchestrator

ATTENDANCE_HTML = (
    '<html><body><table id="attendanceTable">'
    "<tr><th>S.No</th><th>Code</th><th>Title</th><th>Type</th>"
    "<th>Attended</th><th>Total</th><th>Percentage</th></tr>"
    "<tr><td>1</td><td>CSE1001</td><td>Test</td><td>TH</td>"
    "<td>40</td><td>45</td><td>88.89%</td></tr>"
    "</table></body></html>"
)


@settings(max_examples=100)
@given(csrf_token=text(alphabet="abcdefghijklmnop0123456789-_", min_size=10, max_size=40))
def test_csrf_token_included_in_all_post_requests(csrf_token):
    """All POST requests from SyncOrchestrator include _csrf field with
    a non-empty value matching the most recently extracted CSRF token.

    **Validates: Requirements 6.5**
    """
    store = AsyncMock()
    orchestrator = SyncOrchestrator(store)

    # Setup mock client
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/something"
    mock_resp.text = ATTENDANCE_HTML
    mock_client.post = AsyncMock(return_value=mock_resp)

    orchestrator.client = mock_client
    orchestrator._csrf = csrf_token

    # Call a scrape method that issues a POST request
    asyncio.run(
        orchestrator._scrape_attendance("SEM1")
    )

    # Verify the POST was called with _csrf in data
    call_kwargs = mock_client.post.call_args
    data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
    assert "_csrf" in data, "POST request must include _csrf field"
    assert data["_csrf"] == csrf_token, "CSRF token must match the stored token"
    assert len(data["_csrf"]) > 0, "CSRF token must be non-empty"

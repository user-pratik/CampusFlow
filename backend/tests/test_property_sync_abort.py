"""Property-based test for sync abort on login redirect preserving data integrity.

Feature: embedded-vtop-login, Property 10: Sync abort on login redirect preserves data integrity

For any sequence of scraping requests where one returns a login redirect,
the SyncOrchestrator SHALL NOT persist any data from the current sync attempt
(including data from endpoints that succeeded before the redirect),
and SHALL mark the session as expired.

Validates: Requirements 6.4
"""

import asyncio

import pytest
from hypothesis import given, settings
from hypothesis.strategies import sampled_from
from unittest.mock import AsyncMock, MagicMock

from app.connectors.vtop.sync_orchestrator import SyncOrchestrator


# ─── Sample HTML Fixtures ─────────────────────────────────────────────────────

ATTENDANCE_HTML = (
    '<html><body><table id="attendanceTable">'
    "<tr><th>S.No</th><th>Code</th><th>Title</th><th>Type</th>"
    "<th>Attended</th><th>Total</th><th>Percentage</th></tr>"
    "<tr><td>1</td><td>CSE1001</td><td>Problem Solving</td><td>TH</td>"
    "<td>40</td><td>45</td><td>88.89%</td></tr>"
    "</table></body></html>"
)

MARKS_HTML = (
    '<html><body><table id="marksTable">'
    "<tr><th>S.No</th><th>Code</th><th>Title</th><th>CAT1</th>"
    "<th>CAT2</th><th>Total</th></tr>"
    "<tr><td>1</td><td>CSE1001</td><td>Problem Solving</td>"
    "<td>45</td><td>42</td><td>87</td></tr>"
    "</table></body></html>"
)

CGPA_HTML = (
    "<html><body>"
    "<p>CGPA: 8.75</p>"
    "<p>Total Credits Earned: 120</p>"
    "</body></html>"
)

LOGIN_HTML = '<html><body><form action="/vtop/login">Login</form></body></html>'

# The three scraping steps in order
STEP_HTMLS = [ATTENDANCE_HTML, MARKS_HTML, CGPA_HTML]
STEP_URLS = [
    "https://vtopcc.vit.ac.in/vtop/academics/common/getAttendance",
    "https://vtopcc.vit.ac.in/vtop/academics/common/getMarksView",
    "https://vtopcc.vit.ac.in/vtop/academics/common/getGradeHistory",
]
LOGIN_URL = "https://vtopcc.vit.ac.in/vtop/login"


# ─── Property Test ────────────────────────────────────────────────────────────


@settings(max_examples=100)
@given(fail_at_step=sampled_from([0, 1, 2]))
def test_sync_abort_no_data_persisted(fail_at_step):
    """For any scraping step that returns a login redirect, no data from the current
    sync attempt SHALL be persisted (including data from prior successful steps),
    and the session SHALL be marked as expired.

    **Validates: Requirements 6.4**
    """
    # Build response sequence: success for steps before fail_at_step, login redirect at fail_at_step
    responses = []
    for i in range(3):
        resp = MagicMock()
        if i == fail_at_step:
            resp.url = LOGIN_URL
            resp.text = LOGIN_HTML
        else:
            resp.url = STEP_URLS[i]
            resp.text = STEP_HTMLS[i]
        responses.append(resp)

    # Setup orchestrator with mock session store
    store = AsyncMock()
    store.get_cookies_as_httpx.return_value = MagicMock()  # non-None (valid session)
    store.mark_expired = AsyncMock()

    orchestrator = SyncOrchestrator(store)
    orchestrator.client = AsyncMock()
    orchestrator.client.post = AsyncMock(side_effect=responses)
    orchestrator._csrf = "test-csrf-token"

    # Spy on persist methods to verify they are NOT called
    orchestrator._persist_attendance = AsyncMock()
    orchestrator._persist_marks = AsyncMock()
    orchestrator._persist_profile = AsyncMock()

    # Run the sync
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(orchestrator.sync_all("SEM1"))
    finally:
        loop.close()

    # Assertions: sync must abort with session_expired
    assert result.status == "session_expired", (
        f"Expected status 'session_expired' when step {fail_at_step} returns login redirect, "
        f"but got '{result.status}'"
    )

    # No data should be persisted regardless of which step failed
    orchestrator._persist_attendance.assert_not_called(), (
        f"Attendance should NOT be persisted when step {fail_at_step} redirects to login"
    )
    orchestrator._persist_marks.assert_not_called(), (
        f"Marks should NOT be persisted when step {fail_at_step} redirects to login"
    )
    orchestrator._persist_profile.assert_not_called(), (
        f"Profile should NOT be persisted when step {fail_at_step} redirects to login"
    )

    # Session must be marked as expired
    store.mark_expired.assert_called(), (
        f"Session should be marked as expired when step {fail_at_step} redirects to login"
    )

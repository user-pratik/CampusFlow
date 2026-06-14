"""Tests for SyncOrchestrator — HTTP-based VTOP scraping.

Tests cover:
- CSRF token extraction
- Login redirect detection
- Semester fetching
- Sync flow with mocked HTTP responses
- Persistence logic (empty data preservation)
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from app.connectors.vtop.sync_orchestrator import SyncOrchestrator, SyncResult


# ─── Sample HTML Fixtures ─────────────────────────────────────────────────────

CONTENT_PAGE_HTML = """
<html>
<head><meta name="_csrf" content="test-csrf-token-123"></head>
<body><h1>VTOP Student Portal</h1></body>
</html>
"""

SEMESTER_HTML = """
<html><body>
<select id="semesterSubId">
  <option value="0">--Select--</option>
  <option value="AP2024251">Fall Semester 2024-25</option>
  <option value="AP2024252">Winter Semester 2024-25</option>
</select>
</body></html>
"""

ATTENDANCE_HTML = """
<html><body>
<table id="attendanceTable">
  <tr><th>S.No</th><th>Code</th><th>Title</th><th>Type</th><th>Attended</th><th>Total</th><th>Percentage</th></tr>
  <tr><td>1</td><td>CSE1001</td><td>Problem Solving</td><td>TH</td><td>40</td><td>45</td><td>88.89%</td></tr>
  <tr><td>2</td><td>CSE1002</td><td>Data Structures</td><td>TH</td><td>38</td><td>42</td><td>90.48%</td></tr>
</table>
</body></html>
"""

MARKS_HTML = """
<html><body>
<table id="marksTable">
  <tr><th>S.No</th><th>Code</th><th>Title</th><th>CAT1</th><th>CAT2</th><th>Total</th></tr>
  <tr><td>1</td><td>CSE1001</td><td>Problem Solving</td><td>45</td><td>42</td><td>87</td></tr>
</table>
</body></html>
"""

CGPA_HTML = """
<html><body>
<p>CGPA: 8.75</p>
<p>Total Credits Earned: 120</p>
</body></html>
"""

LOGIN_PAGE_HTML = """
<html><body><form action="/vtop/login">Login Form</form></body></html>
"""


# ─── Helper to create mock session store ──────────────────────────────────────


def make_mock_session_store():
    """Create a mock SessionStore with valid cookies."""
    store = AsyncMock()
    cookies = httpx.Cookies()
    cookies.set("JSESSIONID", "abc123", domain="vtopcc.vit.ac.in", path="/")
    store.get_cookies_as_httpx.return_value = cookies
    store.mark_expired = AsyncMock()
    return store


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestSyncOrchestratorHelpers:
    """Test helper/utility methods."""

    def test_is_login_redirect_detected(self):
        """Login redirect URL is correctly detected."""
        orchestrator = SyncOrchestrator(AsyncMock())
        mock_resp = MagicMock()
        mock_resp.url = "https://vtopcc.vit.ac.in/vtop/login"
        assert orchestrator._is_login_redirect(mock_resp) is True

    def test_is_login_redirect_not_detected(self):
        """Non-login URL is not flagged as redirect."""
        orchestrator = SyncOrchestrator(AsyncMock())
        mock_resp = MagicMock()
        mock_resp.url = "https://vtopcc.vit.ac.in/vtop/content"
        assert orchestrator._is_login_redirect(mock_resp) is False

    def test_extract_csrf_from_input(self):
        """CSRF extracted from hidden input field."""
        from bs4 import BeautifulSoup

        orchestrator = SyncOrchestrator(AsyncMock())
        html = '<html><body><input name="_csrf" value="token123"/></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert orchestrator._extract_csrf(soup) == "token123"

    def test_extract_csrf_from_meta(self):
        """CSRF extracted from meta tag."""
        from bs4 import BeautifulSoup

        orchestrator = SyncOrchestrator(AsyncMock())
        html = '<html><head><meta name="_csrf" content="meta-token"/></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert orchestrator._extract_csrf(soup) == "meta-token"

    def test_extract_csrf_missing(self):
        """Returns empty string when no CSRF found."""
        from bs4 import BeautifulSoup

        orchestrator = SyncOrchestrator(AsyncMock())
        html = "<html><body>No CSRF here</body></html>"
        soup = BeautifulSoup(html, "lxml")
        assert orchestrator._extract_csrf(soup) == ""


class TestSyncOrchestratorGetSemesters:
    """Test semester fetching."""

    @pytest.mark.asyncio
    async def test_get_semesters_success(self):
        """Successfully parses semesters from VTOP response."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        # Mock httpx responses
        with patch("app.connectors.vtop.sync_orchestrator.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            # First call: GET /vtop/content for CSRF
            content_resp = MagicMock()
            content_resp.url = "https://vtopcc.vit.ac.in/vtop/content"
            content_resp.text = CONTENT_PAGE_HTML

            # Second call: POST semesters
            semester_resp = MagicMock()
            semester_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getStudentSemester"
            semester_resp.text = SEMESTER_HTML

            mock_client.get = AsyncMock(return_value=content_resp)
            mock_client.post = AsyncMock(return_value=semester_resp)

            orchestrator.client = mock_client
            orchestrator._csrf = "test-csrf-token-123"

            semesters = await orchestrator.get_semesters()
            assert "Fall Semester 2024-25" in semesters
            assert semesters["Fall Semester 2024-25"] == "AP2024251"
            assert len(semesters) == 2

    @pytest.mark.asyncio
    async def test_get_semesters_session_expired(self):
        """Returns empty dict when session is expired."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        mock_client = AsyncMock()
        semester_resp = MagicMock()
        semester_resp.url = "https://vtopcc.vit.ac.in/vtop/login"
        semester_resp.text = LOGIN_PAGE_HTML
        mock_client.post = AsyncMock(return_value=semester_resp)

        orchestrator.client = mock_client
        orchestrator._csrf = "some-token"

        semesters = await orchestrator.get_semesters()
        assert semesters == {}
        store.mark_expired.assert_called_once()


class TestSyncOrchestratorSyncAll:
    """Test the full sync_all flow."""

    @pytest.mark.asyncio
    async def test_sync_all_completed(self):
        """sync_all returns completed status with correct counts."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        mock_client = AsyncMock()

        # Attendance response
        att_resp = MagicMock()
        att_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getAttendance"
        att_resp.text = ATTENDANCE_HTML

        # Marks response
        marks_resp = MagicMock()
        marks_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getMarksView"
        marks_resp.text = MARKS_HTML

        # CGPA response
        cgpa_resp = MagicMock()
        cgpa_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getGradeHistory"
        cgpa_resp.text = CGPA_HTML

        mock_client.post = AsyncMock(side_effect=[att_resp, marks_resp, cgpa_resp])

        orchestrator.client = mock_client
        orchestrator._csrf = "test-token"

        # Mock persistence methods to avoid DB calls
        orchestrator._persist_attendance = AsyncMock()
        orchestrator._persist_marks = AsyncMock()
        orchestrator._persist_profile = AsyncMock()

        result = await orchestrator.sync_all("AP2024251")

        assert result.status == "completed"
        assert result.attendance_count == 2
        assert result.marks_count == 1
        assert result.profile_updated is True

    @pytest.mark.asyncio
    async def test_sync_all_session_expired_on_attendance(self):
        """sync_all aborts with session_expired when attendance scrape redirects to login."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        mock_client = AsyncMock()
        login_resp = MagicMock()
        login_resp.url = "https://vtopcc.vit.ac.in/vtop/login"
        login_resp.text = LOGIN_PAGE_HTML
        mock_client.post = AsyncMock(return_value=login_resp)

        orchestrator.client = mock_client
        orchestrator._csrf = "test-token"

        result = await orchestrator.sync_all("AP2024251")

        assert result.status == "session_expired"
        store.mark_expired.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_all_no_session(self):
        """sync_all returns session_expired when no cookies available."""
        store = AsyncMock()
        store.get_cookies_as_httpx.return_value = None
        orchestrator = SyncOrchestrator(store)

        result = await orchestrator.sync_all("AP2024251")
        assert result.status == "session_expired"


class TestSyncAbortAndDataIntegrity:
    """Tests for Req 6.4: sync abort discards all unpersisted data."""

    @pytest.mark.asyncio
    async def test_abort_on_marks_redirect_discards_attendance(self):
        """When marks scrape redirects to login, attendance data is NOT persisted.

        Req 6.4: On login redirect at ANY step, abort entire sync,
        discard data from endpoints that succeeded before the redirect.
        """
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        mock_client = AsyncMock()

        # Attendance succeeds
        att_resp = MagicMock()
        att_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getAttendance"
        att_resp.text = ATTENDANCE_HTML

        # Marks redirects to login (session expired)
        marks_resp = MagicMock()
        marks_resp.url = "https://vtopcc.vit.ac.in/vtop/login"
        marks_resp.text = LOGIN_PAGE_HTML

        mock_client.post = AsyncMock(side_effect=[att_resp, marks_resp])

        orchestrator.client = mock_client
        orchestrator._csrf = "test-token"

        # Spy on persistence methods to confirm they're NOT called
        orchestrator._persist_attendance = AsyncMock()
        orchestrator._persist_marks = AsyncMock()
        orchestrator._persist_profile = AsyncMock()

        result = await orchestrator.sync_all("AP2024251")

        assert result.status == "session_expired"
        # Critical: no data should be persisted when sync is aborted
        orchestrator._persist_attendance.assert_not_called()
        orchestrator._persist_marks.assert_not_called()
        orchestrator._persist_profile.assert_not_called()
        store.mark_expired.assert_called()

    @pytest.mark.asyncio
    async def test_abort_on_cgpa_redirect_discards_all(self):
        """When CGPA scrape redirects to login, attendance AND marks NOT persisted.

        Req 6.4: Even though attendance and marks scraping succeeded,
        none of that data is persisted because sync is aborted.
        """
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        mock_client = AsyncMock()

        # Attendance succeeds
        att_resp = MagicMock()
        att_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getAttendance"
        att_resp.text = ATTENDANCE_HTML

        # Marks succeeds
        marks_resp = MagicMock()
        marks_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getMarksView"
        marks_resp.text = MARKS_HTML

        # CGPA redirects to login (session expired)
        cgpa_resp = MagicMock()
        cgpa_resp.url = "https://vtopcc.vit.ac.in/vtop/login"
        cgpa_resp.text = LOGIN_PAGE_HTML

        mock_client.post = AsyncMock(side_effect=[att_resp, marks_resp, cgpa_resp])

        orchestrator.client = mock_client
        orchestrator._csrf = "test-token"

        orchestrator._persist_attendance = AsyncMock()
        orchestrator._persist_marks = AsyncMock()
        orchestrator._persist_profile = AsyncMock()

        result = await orchestrator.sync_all("AP2024251")

        assert result.status == "session_expired"
        # No data persisted even though attendance and marks succeeded
        orchestrator._persist_attendance.assert_not_called()
        orchestrator._persist_marks.assert_not_called()
        orchestrator._persist_profile.assert_not_called()
        store.mark_expired.assert_called()

    @pytest.mark.asyncio
    async def test_session_expired_error_message(self):
        """Abort returns descriptive error message identifying the failed step."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        mock_client = AsyncMock()
        login_resp = MagicMock()
        login_resp.url = "https://vtopcc.vit.ac.in/vtop/login"
        login_resp.text = LOGIN_PAGE_HTML
        mock_client.post = AsyncMock(return_value=login_resp)

        orchestrator.client = mock_client
        orchestrator._csrf = "test-token"

        result = await orchestrator.sync_all("AP2024251")

        assert result.status == "session_expired"
        assert result.error is not None
        assert "session expired" in result.error.lower() or "re-authentication" in result.error.lower()


class TestEmptyDataPreservation:
    """Tests for Req 6.6: empty data skips persistence, preserves existing."""

    @pytest.mark.asyncio
    async def test_empty_attendance_skips_persistence(self):
        """Empty attendance list does not trigger delete of existing records.

        Req 6.6: If VTOP returns valid HTML with no data rows,
        skip persistence for that type, preserve existing records.
        """
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        # Call _persist_attendance with empty list - should be a no-op
        with patch("app.connectors.vtop.sync_orchestrator.async_session_maker") as mock_session_maker:
            await orchestrator._persist_attendance([])
            # Session maker should NOT be called (no DB interaction)
            mock_session_maker.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_marks_skips_persistence(self):
        """Empty marks list does not trigger delete of existing records."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        with patch("app.connectors.vtop.sync_orchestrator.async_session_maker") as mock_session_maker:
            await orchestrator._persist_marks([])
            mock_session_maker.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_profile_skips_persistence(self):
        """Zero CGPA and zero credits does not trigger delete of existing profile."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        with patch("app.connectors.vtop.sync_orchestrator.async_session_maker") as mock_session_maker:
            await orchestrator._persist_profile({"cgpa": 0, "total_credits": 0})
            mock_session_maker.assert_not_called()

    @pytest.mark.asyncio
    async def test_nonempty_attendance_triggers_persistence(self):
        """Non-empty attendance DOES trigger persistence (delete + insert)."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        with patch("app.connectors.vtop.sync_orchestrator.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

            records = [{"course_code": "CSE1001", "course_title": "Intro CS", "percentage": 90.0, "attended": 36, "total": 40}]
            await orchestrator._persist_attendance(records)

            # Session maker SHOULD be called for non-empty records
            mock_session_maker.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_all_with_empty_attendance_preserves_existing(self):
        """sync_all with empty attendance response skips attendance persistence.

        Req 6.6: Parser returns empty list → persistence is skipped.
        Other data types still persist normally.
        """
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        mock_client = AsyncMock()

        # Attendance response with no data rows (empty HTML table)
        empty_att_html = "<html><body><table></table></body></html>"
        att_resp = MagicMock()
        att_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getAttendance"
        att_resp.text = empty_att_html

        # Marks response (has data)
        marks_resp = MagicMock()
        marks_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getMarksView"
        marks_resp.text = MARKS_HTML

        # CGPA response (has data)
        cgpa_resp = MagicMock()
        cgpa_resp.url = "https://vtopcc.vit.ac.in/vtop/academics/common/getGradeHistory"
        cgpa_resp.text = CGPA_HTML

        mock_client.post = AsyncMock(side_effect=[att_resp, marks_resp, cgpa_resp])

        orchestrator.client = mock_client
        orchestrator._csrf = "test-token"

        # Spy on persist methods
        orchestrator._persist_attendance = AsyncMock()
        orchestrator._persist_marks = AsyncMock()
        orchestrator._persist_profile = AsyncMock()

        result = await orchestrator.sync_all("AP2024251")

        assert result.status == "completed"
        # _persist_attendance is called with empty list (it internally skips)
        orchestrator._persist_attendance.assert_called_once_with([])
        # Other types are persisted normally
        orchestrator._persist_marks.assert_called_once()
        orchestrator._persist_profile.assert_called_once()


class TestSingleTransactionPersistence:
    """Tests for Req 6.3: replace all records in a single transaction."""

    @pytest.mark.asyncio
    async def test_persist_attendance_single_commit(self):
        """Attendance persistence uses exactly one commit (atomic transaction).

        Req 6.3: Replace all existing records per data type in a single transaction.
        """
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        with patch("app.connectors.vtop.sync_orchestrator.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

            records = [
                {"course_code": "CSE1001", "course_title": "Intro CS", "percentage": 90.0, "attended": 36, "total": 40},
                {"course_code": "CSE1002", "course_title": "Data Structures", "percentage": 85.0, "attended": 34, "total": 40},
            ]
            await orchestrator._persist_attendance(records)

            # Exactly one commit — delete + all inserts in single transaction
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_marks_single_commit(self):
        """Marks persistence uses exactly one commit (atomic transaction)."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        with patch("app.connectors.vtop.sync_orchestrator.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

            records = [
                {"course_code": "CSE1001", "course_title": "Intro CS", "mark_title": "CAT1", "max_mark": 50, "score": 45},
                {"course_code": "CSE1001", "course_title": "Intro CS", "mark_title": "CAT2", "max_mark": 50, "score": 42},
            ]
            await orchestrator._persist_marks(records)

            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_profile_single_commit(self):
        """Profile persistence uses exactly one commit (atomic transaction)."""
        store = make_mock_session_store()
        orchestrator = SyncOrchestrator(store)

        with patch("app.connectors.vtop.sync_orchestrator.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

            data = {"cgpa": 8.75, "total_credits": 120}
            await orchestrator._persist_profile(data)

            mock_session.commit.assert_called_once()


class TestSyncResult:
    """Test SyncResult model."""

    def test_default_values(self):
        """SyncResult has correct defaults."""
        result = SyncResult(status="completed")
        assert result.attendance_count == 0
        assert result.marks_count == 0
        assert result.profile_updated is False
        assert result.error is None

    def test_full_values(self):
        """SyncResult accepts all fields."""
        result = SyncResult(
            status="failed",
            attendance_count=5,
            marks_count=10,
            profile_updated=True,
            error="Something went wrong",
        )
        assert result.status == "failed"
        assert result.error == "Something went wrong"

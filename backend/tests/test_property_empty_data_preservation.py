"""Property-based test for empty data preservation.

Feature: embedded-vtop-login, Property 12: Empty data response preserves existing records

Validates: Requirements 6.6

For any VTOP HTML response that is valid but contains zero data rows for a given
data type, the SyncOrchestrator SHALL NOT delete existing database records for
that data type.

We verify this by calling _persist_attendance, _persist_marks, and _persist_profile
with empty/zero inputs and asserting that async_session_maker is never called,
meaning existing database records are left untouched.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings
from hypothesis.strategies import sampled_from

from app.connectors.vtop.sync_orchestrator import SyncOrchestrator


@settings(max_examples=100)
@given(data_type=sampled_from(["attendance", "marks", "profile"]))
def test_empty_data_does_not_touch_db(data_type):
    """When persist methods receive empty data, the DB session is never opened.

    This guarantees that existing records are preserved when VTOP returns
    valid HTML with no data rows for a given data type.

    - attendance: empty list means no rows parsed
    - marks: empty list means no rows parsed
    - profile: cgpa=0 and total_credits=0 means no meaningful data

    **Validates: Requirements 6.6**
    """
    orchestrator = SyncOrchestrator(AsyncMock())

    with patch(
        "app.connectors.vtop.sync_orchestrator.async_session_maker"
    ) as mock_session_maker:
        if data_type == "attendance":
            asyncio.run(orchestrator._persist_attendance([]))
        elif data_type == "marks":
            asyncio.run(orchestrator._persist_marks([]))
        else:
            # Profile with zero cgpa and zero credits = no meaningful data
            asyncio.run(
                orchestrator._persist_profile({"cgpa": 0, "total_credits": 0})
            )

        # DB session maker should NOT be called — no DB interaction at all
        mock_session_maker.assert_not_called()

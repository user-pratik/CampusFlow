"""Tests for GET /api/vtop/semesters and POST /api/vtop/sync endpoints.

Validates Requirements 5.1, 6.1, 6.2, 6.3.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.connectors.vtop.sync_orchestrator import SyncResult

PATCH_GET_SEMESTERS = (
    "app.connectors.vtop.sync_orchestrator.SyncOrchestrator.get_semesters"
)
PATCH_SYNC_ALL = "app.connectors.vtop.sync_orchestrator.SyncOrchestrator.sync_all"
PATCH_CLOSE = "app.connectors.vtop.sync_orchestrator.SyncOrchestrator.close"


@pytest.mark.asyncio
async def test_get_semesters_success(client):
    """Returns semester mapping when session is active."""
    mock_semesters = {
        "Fall Semester 2024-25": "AP2024251",
        "Winter Semester 2024-25": "AP2024252",
    }
    with (
        patch(PATCH_GET_SEMESTERS, new_callable=AsyncMock, return_value=mock_semesters),
        patch(PATCH_CLOSE, new_callable=AsyncMock),
    ):
        response = await client.get("/api/vtop/semesters")

    assert response.status_code == 200
    data = response.json()
    assert data["semesters"] == mock_semesters
    assert data["error"] is None


@pytest.mark.asyncio
async def test_get_semesters_empty(client):
    """Returns empty dict when no session or session expired."""
    with (
        patch(PATCH_GET_SEMESTERS, new_callable=AsyncMock, return_value={}),
        patch(PATCH_CLOSE, new_callable=AsyncMock),
    ):
        response = await client.get("/api/vtop/semesters")

    assert response.status_code == 200
    data = response.json()
    assert data["semesters"] == {}
    assert data["error"] is None


@pytest.mark.asyncio
async def test_get_semesters_exception(client):
    """Returns error field when orchestrator raises."""
    with (
        patch(
            PATCH_GET_SEMESTERS,
            new_callable=AsyncMock,
            side_effect=RuntimeError("connection lost"),
        ),
        patch(PATCH_CLOSE, new_callable=AsyncMock),
    ):
        response = await client.get("/api/vtop/semesters")

    assert response.status_code == 200
    data = response.json()
    assert data["semesters"] == {}
    assert "connection lost" in data["error"]


@pytest.mark.asyncio
async def test_sync_completed(client):
    """Returns SyncResult with counts on successful sync."""
    mock_result = SyncResult(
        status="completed",
        attendance_count=8,
        marks_count=15,
        profile_updated=True,
    )
    with (
        patch(PATCH_SYNC_ALL, new_callable=AsyncMock, return_value=mock_result),
        patch(PATCH_CLOSE, new_callable=AsyncMock),
    ):
        response = await client.post(
            "/api/vtop/sync", json={"semester_id": "AP2024251"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["attendance_count"] == 8
    assert data["marks_count"] == 15
    assert data["profile_updated"] is True
    assert data["error"] is None


@pytest.mark.asyncio
async def test_sync_session_expired(client):
    """Returns session_expired status when cookies are stale."""
    mock_result = SyncResult(
        status="session_expired",
        error="No valid session — please log in again.",
    )
    with (
        patch(PATCH_SYNC_ALL, new_callable=AsyncMock, return_value=mock_result),
        patch(PATCH_CLOSE, new_callable=AsyncMock),
    ):
        response = await client.post(
            "/api/vtop/sync", json={"semester_id": "AP2024251"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "session_expired"
    assert data["attendance_count"] == 0
    assert data["marks_count"] == 0
    assert "log in" in data["error"]


@pytest.mark.asyncio
async def test_sync_missing_semester_id(client):
    """Returns 422 when semester_id is not provided in the body."""
    response = await client.post("/api/vtop/sync", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_failed(client):
    """Returns failed status with error message on sync failure."""
    mock_result = SyncResult(
        status="failed",
        error="Request timed out.",
    )
    with (
        patch(PATCH_SYNC_ALL, new_callable=AsyncMock, return_value=mock_result),
        patch(PATCH_CLOSE, new_callable=AsyncMock),
    ):
        response = await client.post(
            "/api/vtop/sync", json={"semester_id": "AP2024251"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert "timed out" in data["error"]

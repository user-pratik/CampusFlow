"""Tests for GET /api/vtop/session-status endpoint.

Validates Requirements 4.3, 4.4, 4.5, 7.1, 7.2.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.connectors.vtop.session_validator import SessionStatus

PATCH_TARGET = "app.connectors.vtop.session_validator.SessionValidator.validate"


@pytest.mark.asyncio
async def test_session_status_valid(client):
    """Returns status 'valid' when session cookies are still authenticated."""
    mock_result = SessionStatus(
        status="valid", established_at="2024-01-01T12:00:00"
    )
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=mock_result):
        response = await client.get("/api/vtop/session-status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "valid"
    assert data["established_at"] == "2024-01-01T12:00:00"


@pytest.mark.asyncio
async def test_session_status_expired(client):
    """Returns status 'session_expired' when VTOP redirects to login."""
    mock_result = SessionStatus(
        status="session_expired", established_at="2024-01-01T12:00:00"
    )
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=mock_result):
        response = await client.get("/api/vtop/session-status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "session_expired"


@pytest.mark.asyncio
async def test_session_status_no_session(client):
    """Returns status 'no_session' when no stored session exists."""
    mock_result = SessionStatus(status="no_session")
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=mock_result):
        response = await client.get("/api/vtop/session-status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_session"
    assert data["error"] is None
    assert data["established_at"] is None


@pytest.mark.asyncio
async def test_session_status_validation_failed(client):
    """Returns status 'validation_failed' with error on network issues."""
    mock_result = SessionStatus(
        status="validation_failed",
        error="VTOP is unreachable: request timed out",
    )
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=mock_result):
        response = await client.get("/api/vtop/session-status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "validation_failed"
    assert "unreachable" in data["error"]


@pytest.mark.asyncio
async def test_session_status_response_model(client):
    """Response matches the SessionStatus model schema."""
    mock_result = SessionStatus(status="valid", established_at="2024-06-15T10:30:00")
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=mock_result):
        response = await client.get("/api/vtop/session-status")

    data = response.json()
    # Verify all expected keys exist in response
    assert "status" in data
    assert "error" in data
    assert "established_at" in data
    # Status must be one of the valid literals
    assert data["status"] in ("valid", "session_expired", "no_session", "validation_failed")

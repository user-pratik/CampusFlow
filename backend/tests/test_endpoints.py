"""Tests for CampusFlow API endpoints.

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 7.1
"""

import pytest


@pytest.mark.asyncio
async def test_get_profile(client):
    """GET /api/profile returns 200 with profile data."""
    response = await client.get("/api/profile")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "branch" in data


@pytest.mark.asyncio
async def test_get_notices_empty(client):
    """GET /api/notices returns 200 with empty list when no data exists."""
    response = await client.get("/api/notices")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_tasks_empty(client):
    """GET /api/tasks returns 200 with empty list when no data exists."""
    response = await client.get("/api/tasks")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_digest_latest_no_data(client):
    """GET /api/digest/latest returns 200 with 'No digest available' message."""
    response = await client.get("/api/digest/latest")
    assert response.status_code == 200
    assert response.json() == {"message": "No digest available"}


@pytest.mark.asyncio
async def test_post_digest_trigger(client):
    """POST /api/digest/trigger returns 200 with a generated digest."""
    response = await client.post("/api/digest/trigger")
    assert response.status_code == 200
    data = response.json()
    # DigestAgent returns a Digest record with content and generated_at
    assert "content" in data
    assert "generated_at" in data
    assert len(data["content"]) > 0

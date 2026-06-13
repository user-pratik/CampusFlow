"""Tests for health endpoint and CORS configuration.

Validates Requirements 1.1 (health check) and 1.2 (CORS headers).
"""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    """GET /health returns 200 with {"status": "healthy"}."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_cors_headers_present(client):
    """CORS headers are present on preflight OPTIONS request."""
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "*"

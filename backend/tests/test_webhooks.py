"""Tests for the WhatsApp webhook endpoint.

Validates:
- POST /api/webhooks/whatsapp returns 200 with correct body
- First payload creates sample_payload.json
- Subsequent payloads do not overwrite existing file

Requirements: 6.1, 6.2, 6.3, 6.4
"""

import json

import pytest

import app.routers.webhooks as webhooks_module


@pytest.mark.asyncio
async def test_webhook_returns_200(client):
    """POST /api/webhooks/whatsapp returns 200 with {"status": "received"}."""
    response = await client.post("/api/webhooks/whatsapp", json={"msg": "hello"})
    assert response.status_code == 200
    assert response.json() == {"status": "received"}


@pytest.mark.asyncio
async def test_first_payload_creates_file(client, monkeypatch, tmp_path):
    """First webhook payload creates sample_payload.json in backend root."""
    sample_file = tmp_path / "sample_payload.json"
    monkeypatch.setattr(webhooks_module, "SAMPLE_PAYLOAD_PATH", sample_file)

    payload = {"test": "data", "number": 42}
    response = await client.post("/api/webhooks/whatsapp", json=payload)

    assert response.status_code == 200
    assert sample_file.exists()
    saved = json.loads(sample_file.read_text(encoding="utf-8"))
    assert saved == payload


@pytest.mark.asyncio
async def test_subsequent_payload_no_overwrite(client, monkeypatch, tmp_path):
    """Subsequent payloads do not overwrite an existing sample_payload.json."""
    sample_file = tmp_path / "sample_payload.json"
    original_content = {"original": "content"}
    sample_file.write_text(json.dumps(original_content), encoding="utf-8")
    monkeypatch.setattr(webhooks_module, "SAMPLE_PAYLOAD_PATH", sample_file)

    response = await client.post("/api/webhooks/whatsapp", json={"new": "data"})

    assert response.status_code == 200
    saved = json.loads(sample_file.read_text(encoding="utf-8"))
    assert saved == original_content  # File was NOT overwritten

"""Tests for the WhatsApp webhook endpoint.

Validates:
- POST /api/webhooks/whatsapp returns 200 with correct body
- Empty text returns "ignored"
- Duplicate messages are dropped
- First payload creates sample_payload.json
- Subsequent payloads do not overwrite existing file

Requirements: 6.1, 6.2, 6.3, 6.4 + Phase 3 deduplication
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

import app.routers.webhooks as webhooks_module


@pytest.mark.asyncio
async def test_webhook_returns_processing(client, monkeypatch, tmp_path):
    """POST /api/webhooks/whatsapp with valid text returns 200 with 'processing'."""
    sample_file = tmp_path / "sample_payload.json"
    monkeypatch.setattr(webhooks_module, "SAMPLE_PAYLOAD_PATH", sample_file)

    # Mock the pipeline so we don't actually call the LLM
    with patch.object(webhooks_module, "_run_pipeline", new_callable=AsyncMock):
        response = await client.post(
            "/api/webhooks/whatsapp",
            json={"text": "Assignment due tomorrow", "group": "CS101"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "processing"}


@pytest.mark.asyncio
async def test_webhook_empty_text_ignored(client):
    """POST with empty text returns 'ignored'."""
    response = await client.post(
        "/api/webhooks/whatsapp",
        json={"text": "", "group": "test"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_webhook_no_text_field_ignored(client):
    """POST without 'text' key returns 'ignored'."""
    response = await client.post("/api/webhooks/whatsapp", json={"msg": "hello"})
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_duplicate_message_dropped(client, test_session, monkeypatch, tmp_path):
    """Second identical message returns 'duplicate dropped'."""
    from app.models import Notice
    from app.utils.hashing import compute_text_hash

    sample_file = tmp_path / "sample_payload.json"
    monkeypatch.setattr(webhooks_module, "SAMPLE_PAYLOAD_PATH", sample_file)

    # Pre-insert a notice with the same hash
    raw = "Exam on Monday 10am"
    notice = Notice(
        text_hash=compute_text_hash(raw),
        source_group="TestGroup",
        raw_text=raw,
        parsed_title="Exam",
        category="Academic",
    )
    test_session.add(notice)
    await test_session.commit()

    response = await client.post(
        "/api/webhooks/whatsapp",
        json={"text": raw, "group": "TestGroup"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "duplicate dropped"}


@pytest.mark.asyncio
async def test_first_payload_creates_file(client, monkeypatch, tmp_path):
    """First webhook payload creates sample_payload.json in backend root."""
    sample_file = tmp_path / "sample_payload.json"
    monkeypatch.setattr(webhooks_module, "SAMPLE_PAYLOAD_PATH", sample_file)

    payload = {"text": "hello world", "group": "test"}
    with patch.object(webhooks_module, "_run_pipeline", new_callable=AsyncMock):
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

    with patch.object(webhooks_module, "_run_pipeline", new_callable=AsyncMock):
        response = await client.post(
            "/api/webhooks/whatsapp",
            json={"text": "new message", "group": "g"},
        )

    assert response.status_code == 200
    saved = json.loads(sample_file.read_text(encoding="utf-8"))
    assert saved == original_content  # File was NOT overwritten

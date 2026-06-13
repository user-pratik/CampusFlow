"""Webhooks router — handles incoming WhatsApp webhook payloads."""

import json
from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter()

# Resolve backend root (from app/routers/ up to backend/)
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_PAYLOAD_PATH = BACKEND_ROOT / "sample_payload.json"


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request) -> dict:
    """Accept a WhatsApp webhook payload, print it, and optionally save to file."""
    payload = await request.json()

    # Print payload to console
    print(payload)

    # Save to sample_payload.json if it doesn't already exist
    if not SAMPLE_PAYLOAD_PATH.exists():
        with open(SAMPLE_PAYLOAD_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    return {"status": "received"}

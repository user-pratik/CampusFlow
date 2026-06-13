"""Hash deduplication utility for dropping duplicate WhatsApp forwards."""

import hashlib


def compute_text_hash(raw_text: str) -> str:
    """Strip whitespace and compute SHA-256 hash of the text.

    Used to deduplicate incoming messages before they reach the LLM pipeline.

    Args:
        raw_text: The raw message string from WhatsApp.

    Returns:
        Hex-encoded SHA-256 hash of the stripped text.
    """
    cleaned = raw_text.strip()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

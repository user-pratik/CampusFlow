"""Rolling Groq LLM client with automatic key rotation on rate limits.

Uses the native `groq` Python SDK (AsyncGroq) instead of the openai client.
Supports two model tiers:
- FAST model (8B): used for classification, planning, condition detection
- FULL model (70B): used for final response generation by leaf agents
"""

import logging
import os

from groq import AsyncGroq, RateLimitError

logger = logging.getLogger(__name__)

# Parse comma-separated keys from env (supports quoted or plain CSV)
_raw_keys = os.getenv("GROQ_API_KEY", "gsk_REPLACE-ME")
_raw_keys = _raw_keys.strip().strip("[]\"'")
API_KEYS = [k.strip() for k in _raw_keys.split(",") if k.strip()]

# Two-tier model strategy to conserve rate limits
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
FAST_MODEL = os.getenv("GROQ_PLANNER_MODEL", "llama-3.1-8b-instant")

# Build a client pool — one AsyncGroq client per key
_clients = [AsyncGroq(api_key=key) for key in API_KEYS]
_current_index = 0

logger.info("Loaded %d Groq API keys. Full model: %s, Fast model: %s", len(API_KEYS), MODEL, FAST_MODEL)


async def chat_completion(
    messages: list[dict],
    *,
    temperature: float = 0.1,
    max_tokens: int = 1024,
    response_format: dict | None = None,
    timeout: float = 30.0,
    fast: bool = False,
) -> str:
    """Call Groq chat completion with automatic key rotation on rate limit.

    Tries each key once. If all keys are rate-limited, raises the last error.

    Args:
        messages: Chat message list (role + content dicts).
        temperature: Sampling temperature.
        max_tokens: Max completion tokens.
        response_format: Optional format (e.g., {"type": "json_object"}).
        timeout: Request timeout in seconds.
        fast: If True, use the smaller/faster model (8B) for classification tasks.

    Returns:
        The assistant's response content string.

    Raises:
        RateLimitError: If ALL keys are exhausted.
        Exception: Any other non-rate-limit error from the API.
    """
    global _current_index

    model = FAST_MODEL if fast else MODEL
    attempts = len(_clients)
    last_error: Exception | None = None

    for _ in range(attempts):
        client = _clients[_current_index]
        key_suffix = API_KEYS[_current_index][-6:]

        try:
            kwargs: dict = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
                "stream": False,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = await client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            logger.info("Groq call succeeded (key ...%s, model=%s)", key_suffix, model)
            return content or ""

        except RateLimitError as e:
            logger.warning(
                "Key ...%s hit rate limit (model=%s), rotating to next key.", key_suffix, model
            )
            last_error = e
            _current_index = (_current_index + 1) % len(_clients)
            continue

    # All keys exhausted
    raise last_error  # type: ignore[misc]

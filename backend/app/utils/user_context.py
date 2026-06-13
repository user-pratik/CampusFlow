"""User context utility for reading the user profile configuration."""

import json
from pathlib import Path

# Resolve backend root: app/utils/user_context.py -> app/utils -> app -> backend
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
USER_PROFILE_PATH = BACKEND_ROOT / "user_profile.json"


def get_user_profile() -> dict:
    """Read and return the user profile from user_profile.json.

    Returns:
        dict: The parsed user profile data.

    Raises:
        FileNotFoundError: If user_profile.json does not exist at the backend root.
        ValueError: If user_profile.json contains invalid JSON.
    """
    if not USER_PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"User profile not found at {USER_PROFILE_PATH}. "
            "Please create a user_profile.json file in the backend root directory."
        )

    raw_content = USER_PROFILE_PATH.read_text(encoding="utf-8")

    try:
        profile = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in user profile at {USER_PROFILE_PATH}: {e}"
        ) from e

    return profile

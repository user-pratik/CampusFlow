"""User context utility for reading the user profile configuration."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Resolve backend root: app/utils/user_context.py -> app/utils -> app -> backend
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
USER_PROFILE_PATH = BACKEND_ROOT / "user_profile.json"
USER_PROFILE_EXAMPLE_PATH = BACKEND_ROOT / "user_profile.example.json"

_DEFAULT_PROFILE = {
    "name": "Student",
    "reg_no": "",
    "branch": "Not set",
    "college": "VIT",
    "interests": [],
    "current_focus": "",
    "year": 1,
    "semester": 1,
}


def get_user_profile() -> dict:
    """Read and return the user profile from user_profile.json.

    Returns:
        dict: The parsed user profile data. Falls back to defaults if file is missing.

    Raises:
        ValueError: If user_profile.json contains invalid JSON.
    """
    if not USER_PROFILE_PATH.exists():
        # Try to copy from example, otherwise use defaults
        if USER_PROFILE_EXAMPLE_PATH.exists():
            import shutil
            shutil.copy2(USER_PROFILE_EXAMPLE_PATH, USER_PROFILE_PATH)
            logger.info("Created user_profile.json from example template. Edit it with your info.")
        else:
            logger.warning(
                "No user_profile.json found. Using defaults. "
                "Create one from user_profile.example.json for personalized responses."
            )
            return _DEFAULT_PROFILE.copy()

    raw_content = USER_PROFILE_PATH.read_text(encoding="utf-8")

    try:
        profile = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in user profile at {USER_PROFILE_PATH}: {e}"
        ) from e

    return profile

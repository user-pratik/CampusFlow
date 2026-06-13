"""Tests for user profile utility (get_user_profile).

Validates:
- Requirements 4.1: Profile reading from JSON file
- Requirements 4.2: Profile contains expected fields
- Requirements 4.3: Error handling for missing/invalid files
"""

import json
from pathlib import Path

import pytest

import app.utils.user_context as user_context_module
from app.utils.user_context import get_user_profile


class TestGetUserProfileHappyPath:
    """Test that get_user_profile() returns a valid dict with expected keys."""

    def test_returns_dict(self):
        """get_user_profile() should return a dictionary."""
        profile = get_user_profile()
        assert isinstance(profile, dict)

    def test_has_expected_keys(self):
        """Profile dict should contain the required fields."""
        profile = get_user_profile()
        expected_keys = {"name", "branch", "college", "interests", "current_focus"}
        assert expected_keys.issubset(profile.keys())

    def test_interests_is_list(self):
        """The interests field should be a list."""
        profile = get_user_profile()
        assert isinstance(profile["interests"], list)


class TestGetUserProfileMissingFile:
    """Test that missing profile file raises FileNotFoundError."""

    def test_missing_file_raises_file_not_found(self, monkeypatch, tmp_path):
        """FileNotFoundError raised when user_profile.json does not exist."""
        non_existent = tmp_path / "does_not_exist.json"
        monkeypatch.setattr(user_context_module, "USER_PROFILE_PATH", non_existent)

        with pytest.raises(FileNotFoundError):
            get_user_profile()


class TestGetUserProfileInvalidJSON:
    """Test that invalid JSON in profile file raises ValueError."""

    def test_invalid_json_raises_value_error(self, monkeypatch, tmp_path):
        """ValueError raised when user_profile.json contains invalid JSON."""
        bad_file = tmp_path / "bad_profile.json"
        bad_file.write_text("{invalid json content", encoding="utf-8")
        monkeypatch.setattr(user_context_module, "USER_PROFILE_PATH", bad_file)

        with pytest.raises(ValueError):
            get_user_profile()

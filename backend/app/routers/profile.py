"""Profile router — exposes user profile data."""

from fastapi import APIRouter

from app.utils.user_context import get_user_profile

router = APIRouter()


@router.get("/profile")
async def read_profile() -> dict:
    """Return the current user profile."""
    return get_user_profile()

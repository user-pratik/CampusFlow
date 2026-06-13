"""Digest router — latest digest retrieval and trigger stub."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Digest

router = APIRouter()


@router.get("/digest/latest", response_model=dict | Digest)
async def get_latest_digest(session: AsyncSession = Depends(get_session)):
    """Return the most recent digest, or a fallback message if none exist."""
    result = await session.exec(
        select(Digest).order_by(Digest.generated_at.desc()).limit(1)
    )
    digest = result.first()
    if digest is None:
        return {"message": "No digest available"}
    return digest


@router.post("/digest/trigger")
async def trigger_digest():
    """Stub endpoint for digest generation trigger."""
    return {"status": "not implemented"}

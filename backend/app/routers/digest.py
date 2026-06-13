"""Digest router — latest digest retrieval and manual generation trigger."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Digest
from app.agents.digest_agent import DigestAgent

router = APIRouter()

_digest_agent = DigestAgent()


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


@router.post("/digest/trigger", response_model=Digest)
async def trigger_digest():
    """Execute DigestAgent immediately and return the new digest.

    This is the hackathon demo trigger — runs synchronously so the
    frontend gets the freshly generated briefing in the response.
    """
    result = await _digest_agent.execute({})

    # Fetch the freshly created digest from DB to return a proper model instance
    from app.database import async_session_maker

    async with async_session_maker() as session:
        db_result = await session.exec(
            select(Digest).where(Digest.id == result["digest_id"])
        )
        digest = db_result.first()

    return digest

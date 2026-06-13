"""Notices router — exposes notice records from the database."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Notice

router = APIRouter()


@router.get("/notices", response_model=list[Notice])
async def list_notices(session: AsyncSession = Depends(get_session)):
    """Return all notice records."""
    result = await session.exec(select(Notice))
    return result.all()

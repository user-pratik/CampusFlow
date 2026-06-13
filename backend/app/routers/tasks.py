"""Tasks router — exposes task records from the database."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Task

router = APIRouter()


@router.get("/tasks", response_model=list[Task])
async def list_tasks(session: AsyncSession = Depends(get_session)):
    """Return all task records."""
    result = await session.exec(select(Task))
    return result.all()

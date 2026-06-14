"""Placements router — sync and list placement drives with prep checklists."""

import json

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import PlacementDrive, PrepChecklist

router = APIRouter()


@router.post("/placements/sync")
async def sync_placements():
    """Run placement drive extraction from Gmail emails.

    Scans PLACEMENT-category emails, extracts drive details via LLM,
    creates PlacementDrive + PrepChecklist entries.
    """
    from app.agents.placement_prep_agent import extract_placement_drives

    results = await extract_placement_drives()

    return {
        "status": "completed",
        "drives_extracted": len(results),
        "details": results,
    }


@router.get("/placements")
async def get_placements(session: AsyncSession = Depends(get_session)):
    """Return all placement drives with their prep checklists and eligibility status.

    Response includes drive details + checklist items + eligibility_status,
    ordered by drive_date (soonest first).
    """
    from app.agents.placement_prep_agent import check_eligibility

    result = await session.exec(
        select(PlacementDrive).order_by(PlacementDrive.drive_date)
    )
    drives = result.all()

    # Fetch all checklists in one query
    checklist_result = await session.exec(select(PrepChecklist))
    all_checklists = checklist_result.all()
    checklist_map: dict[int, list[dict]] = {}
    for cl in all_checklists:
        items = json.loads(cl.items) if cl.items else []
        checklist_map[cl.drive_id] = items

    response = []
    for drive in drives:
        rounds = json.loads(drive.rounds) if drive.rounds else []
        checklist_items = checklist_map.get(drive.id, [])
        completed_count = sum(1 for item in checklist_items if item.get("completed"))
        eligibility_status = check_eligibility(drive)

        response.append({
            "id": drive.id,
            "company_name": drive.company_name,
            "role": drive.role,
            "drive_date": drive.drive_date.isoformat() if drive.drive_date else None,
            "rounds": rounds,
            "status": drive.status,
            "applied": drive.applied,
            "package": drive.package,
            "eligibility": drive.eligibility,
            "eligible_degree": drive.eligible_degree,
            "eligible_batch": drive.eligible_batch,
            "min_cgpa": drive.min_cgpa,
            "eligibility_status": eligibility_status,
            "checklist": {
                "items": checklist_items,
                "total": len(checklist_items),
                "completed": completed_count,
            },
            "created_at": drive.created_at.isoformat(),
        })

    return {
        "drives": response,
        "total": len(response),
        "upcoming": sum(1 for d in response if d["status"] == "upcoming"),
        "eligible_count": sum(1 for d in response if d["eligibility_status"] == "Eligible"),
    }


@router.post("/placements/{drive_id}/applied")
async def toggle_applied(
    drive_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Toggle the applied status of a placement drive."""
    result = await session.exec(
        select(PlacementDrive).where(PlacementDrive.id == drive_id)
    )
    drive = result.first()

    if drive is None:
        return {"error": "Drive not found", "id": drive_id}

    drive.applied = not drive.applied
    drive.status = "applied" if drive.applied else "upcoming"
    session.add(drive)
    await session.commit()

    return {"status": "ok", "id": drive_id, "applied": drive.applied}


@router.patch("/placements/{drive_id}/checklist")
async def toggle_checklist_item(
    drive_id: int,
    item_index: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """Toggle a checklist item's completed state by index.

    Query params:
        item_index: Zero-based index of the item to toggle.
    """
    result = await session.exec(
        select(PrepChecklist).where(PrepChecklist.drive_id == drive_id)
    )
    checklist = result.first()

    if checklist is None:
        return {"error": "Checklist not found for drive", "drive_id": drive_id}

    items = json.loads(checklist.items) if checklist.items else []

    if item_index < 0 or item_index >= len(items):
        return {"error": "Invalid item_index", "max": len(items) - 1}

    items[item_index]["completed"] = not items[item_index]["completed"]
    checklist.items = json.dumps(items)
    session.add(checklist)
    await session.commit()

    return {
        "status": "ok",
        "drive_id": drive_id,
        "item_index": item_index,
        "completed": items[item_index]["completed"],
    }

"""Moodle LMS client for CampusFlow.

Connects to VIT's Moodle instance via the Web Services REST API.
Uses a personal token (generated from User > Security Keys in Moodle).

Auth flow:
  1. Student generates a token at: {MOODLE_URL}/user/managetoken.php
     OR uses: {MOODLE_URL}/login/token.php?username=X&password=Y&service=moodle_mobile_app
  2. Token is stored in MOODLE_TOKEN env var.
  3. All API calls use: {MOODLE_URL}/webservice/rest/server.php?wstoken=TOKEN&wsfunction=...

Key functions used:
  - core_enrol_get_users_courses: list enrolled courses
  - mod_assign_get_assignments: get assignments for given course IDs
  - core_calendar_get_calendar_upcoming_view: upcoming calendar events

LIMITATIONS / KNOWN ISSUES:
  - VIT's Moodle may not expose Web Services to students by default.
    If the admin hasn't enabled the "moodle_mobile_app" external service
    for student role, token generation will fail.
  - Alternative: session-based scraping (like VTOP) using login cookies.
    This is more fragile and not implemented here.
  - If MOODLE_TOKEN is not set or invalid, all functions return empty results
    gracefully (no crashes).
"""

import logging
import os
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

MOODLE_URL = os.getenv("MOODLE_URL", "https://lms.vit.ac.in")
MOODLE_TOKEN = os.getenv("MOODLE_TOKEN", "")

# Moodle REST endpoint
WS_ENDPOINT = f"{MOODLE_URL}/webservice/rest/server.php"


def _is_configured() -> bool:
    """Check if Moodle credentials are available."""
    if not MOODLE_TOKEN:
        logger.debug("MOODLE_TOKEN not set — Moodle connector disabled.")
        return False
    return True


async def _call_moodle(wsfunction: str, params: dict | None = None) -> dict | list | None:
    """Make a Moodle Web Service REST API call.

    Args:
        wsfunction: The Moodle WS function name (e.g. 'mod_assign_get_assignments')
        params: Additional query parameters.

    Returns:
        Parsed JSON response, or None on failure.
    """
    if not _is_configured():
        return None

    query = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
    }
    if params:
        query.update(params)

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            resp = await client.get(WS_ENDPOINT, params=query)

            if resp.status_code != 200:
                logger.warning("Moodle API returned %d for %s", resp.status_code, wsfunction)
                return None

            data = resp.json()

            # Moodle returns errors as {"exception": "...", "errorcode": "...", "message": "..."}
            if isinstance(data, dict) and "exception" in data:
                logger.warning(
                    "Moodle API error (%s): %s — %s",
                    data.get("errorcode"),
                    data.get("message"),
                    wsfunction,
                )
                return None

            return data

    except httpx.TimeoutException:
        logger.error("Moodle API timeout for %s", wsfunction)
        return None
    except Exception as e:
        logger.error("Moodle API call failed (%s): %s", wsfunction, e)
        return None


async def get_enrolled_courses() -> list[dict]:
    """Get all courses the authenticated user is enrolled in.

    Returns:
        List of course dicts: [{id, shortname, fullname}, ...]
    """
    # First get the user's ID
    site_info = await _call_moodle("core_webservice_get_site_info")
    if not site_info or not isinstance(site_info, dict):
        return []

    user_id = site_info.get("userid")
    if not user_id:
        return []

    courses = await _call_moodle("core_enrol_get_users_courses", {"userid": str(user_id)})
    if not courses or not isinstance(courses, list):
        return []

    return [
        {
            "id": c.get("id"),
            "shortname": c.get("shortname", ""),
            "fullname": c.get("fullname", ""),
        }
        for c in courses
        if c.get("id")
    ]


async def get_upcoming_assignments() -> list[dict]:
    """Get upcoming assignments from all enrolled courses.

    Returns:
        List of assignment dicts:
        [{
            course_name, course_code, assignment_name,
            due_date (datetime), description, submission_status
        }, ...]
    """
    if not _is_configured():
        logger.info("Moodle not configured — skipping assignment fetch.")
        return []

    # Step 1: Get enrolled courses
    courses = await get_enrolled_courses()
    if not courses:
        logger.info("No Moodle courses found (or auth failed).")
        return []

    # Step 2: Get assignments for all courses
    course_ids = [str(c["id"]) for c in courses]
    # Moodle expects courseids[0]=1&courseids[1]=2&...
    params = {f"courseids[{i}]": cid for i, cid in enumerate(course_ids)}

    response = await _call_moodle("mod_assign_get_assignments", params)
    if not response or not isinstance(response, dict):
        return []

    # Build course ID → name map
    course_map = {c["id"]: c for c in courses}

    assignments: list[dict] = []
    now = datetime.utcnow()

    for course_data in response.get("courses", []):
        course_id = course_data.get("id")
        course_info = course_map.get(course_id, {})

        for assign in course_data.get("assignments", []):
            due_date_ts = assign.get("duedate", 0)
            if due_date_ts == 0:
                continue  # No due date set

            due_dt = datetime.utcfromtimestamp(due_date_ts)

            # Only include future/recent assignments (not ancient ones)
            if due_dt < now:
                continue

            # Extract intro text (HTML — strip basic tags)
            intro = assign.get("intro", "")
            if intro:
                import re
                intro = re.sub(r"<[^>]+>", "", intro)[:200]

            assignments.append({
                "course_name": course_info.get("fullname", ""),
                "course_code": course_info.get("shortname", ""),
                "assignment_name": assign.get("name", "Unnamed Assignment"),
                "due_date": due_dt,
                "description": intro,
                "moodle_assign_id": assign.get("id"),
                "course_id": course_id,
            })

    # Sort by due date
    assignments.sort(key=lambda a: a["due_date"])
    logger.info("Fetched %d upcoming assignments from Moodle.", len(assignments))
    return assignments

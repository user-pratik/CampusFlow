"""VTOP page scrapers — parse attendance, marks, announcements, grades."""

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def parse_attendance(soup: BeautifulSoup) -> list[dict]:
    """Parse the attendance page into structured records.

    Returns:
        List of dicts with: course_code, course_title, percentage, attended, total
    """
    records = []
    table = soup.find("table", {"id": re.compile(r"attendance", re.I)})
    if not table:
        # Fallback: find any table with attendance-like headers
        tables = soup.find_all("table")
        for t in tables:
            headers = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if "attendance" in " ".join(headers) or "percentage" in " ".join(headers):
                table = t
                break

    if not table:
        logger.warning("Attendance table not found in page.")
        return records

    rows = table.find_all("tr")[1:]  # Skip header row
    for row in rows:
        cols = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cols) >= 6:
            try:
                records.append({
                    "course_code": cols[1],
                    "course_title": cols[2],
                    "attended": int(cols[4]) if cols[4].isdigit() else 0,
                    "total": int(cols[5]) if cols[5].isdigit() else 0,
                    "percentage": float(cols[6].replace("%", "")) if len(cols) > 6 else 0.0,
                })
            except (ValueError, IndexError) as e:
                logger.debug("Skipping attendance row: %s", e)
                continue

    logger.info("Parsed %d attendance records.", len(records))
    return records


def parse_marks(soup: BeautifulSoup) -> list[dict]:
    """Parse the internal marks page into structured records.

    Returns:
        List of dicts with: course_code, course_title, cat1, cat2, assignment, total
    """
    records = []
    table = soup.find("table", {"id": re.compile(r"mark", re.I)})
    if not table:
        tables = soup.find_all("table")
        for t in tables:
            headers = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if "cat" in " ".join(headers) or "mark" in " ".join(headers):
                table = t
                break

    if not table:
        logger.warning("Marks table not found in page.")
        return records

    rows = table.find_all("tr")[1:]
    for row in rows:
        cols = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cols) >= 5:
            try:
                records.append({
                    "course_code": cols[1],
                    "course_title": cols[2],
                    "cat1": _parse_float(cols[3]),
                    "cat2": _parse_float(cols[4]) if len(cols) > 4 else None,
                    "assignment": _parse_float(cols[5]) if len(cols) > 5 else None,
                    "total": _parse_float(cols[-1]),
                })
            except (ValueError, IndexError) as e:
                logger.debug("Skipping marks row: %s", e)
                continue

    logger.info("Parsed %d marks records.", len(records))
    return records


def parse_academic_history(soup: BeautifulSoup) -> dict:
    """Parse the grade history page for CGPA and total credits.

    The VTOP grade history page has a summary table where:
    - First row contains headings (including "Credits Earned" and "CGPA")
    - Second row contains the values

    Returns:
        Dict with: cgpa (float), total_credits (int)
    """
    result = {"cgpa": 0.0, "total_credits": 0}

    # Strategy 1: Look in tables for heading row with "CGPA" or "Credits Earned"
    # This matches the Android app's approach (find last table with 'credits' heading)
    tables = soup.find_all("table")
    for table in reversed(tables):  # Search from last table (summary is typically at bottom)
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Get headings from first row
        headings = [td.get_text(strip=True).lower() for td in rows[0].find_all("td")]
        if not headings:
            headings = [th.get_text(strip=True).lower() for th in rows[0].find_all("th")]

        if not any("credit" in h or "cgpa" in h for h in headings):
            continue

        # Found the summary table — extract values from second row
        values = [td.get_text(strip=True) for td in rows[1].find_all("td")]

        for i, heading in enumerate(headings):
            if i < len(values):
                if "cgpa" in heading:
                    try:
                        result["cgpa"] = float(values[i])
                    except (ValueError, IndexError):
                        pass
                elif "earned" in heading or ("credit" in heading and "registered" not in heading):
                    try:
                        result["total_credits"] = int(values[i])
                    except (ValueError, IndexError):
                        pass

        if result["cgpa"] > 0:
            break

    # Strategy 2: Regex fallback on page text
    if result["cgpa"] == 0.0:
        text = soup.get_text()
        cgpa_match = re.search(r"CGPA[:\s]*(\d+\.?\d*)", text, re.I)
        if cgpa_match:
            result["cgpa"] = float(cgpa_match.group(1))

    if result["total_credits"] == 0:
        text = soup.get_text()
        credits_match = re.search(r"(?:Total\s+)?Credits?\s*(?:Earned)?[:\s]*(\d+)", text, re.I)
        if credits_match:
            result["total_credits"] = int(credits_match.group(1))

    logger.info("Parsed academic profile: CGPA=%.2f, Credits=%d", result["cgpa"], result["total_credits"])

    logger.info("Parsed academic profile: CGPA=%.2f, Credits=%d", result["cgpa"], result["total_credits"])
    return result


def parse_announcements(soup: BeautifulSoup) -> list[dict]:
    """Parse announcements/exam schedule into raw messages for the LLM pipeline.

    Returns:
        List of dicts with: raw_text, source_group
    """
    messages = []

    # Look for announcement content — typically in a div or table
    containers = soup.find_all(["div", "td"], class_=re.compile(r"announce|notice|content", re.I))
    if not containers:
        # Fallback: grab all paragraphs or list items in main content
        containers = soup.find_all(["p", "li"])

    for container in containers:
        text = container.get_text(strip=True)
        if len(text) > 20:  # Skip trivially short entries
            messages.append({
                "raw_text": text,
                "source_group": "VTOP Portal",
            })

    logger.info("Parsed %d announcements from VTOP.", len(messages))
    return messages


def parse_timetable(soup: BeautifulSoup) -> list[dict]:
    """Parse the StudentTimeTableChn timetable page into structured slot records.

    VTOP renders a table where:
    - First row = time slot headers (e.g. "08:00-08:50")
    - First column of each subsequent row = day of the week (MON, TUE, etc.)
    - Each cell may contain course info: code, name, venue, slot type

    Returns:
        List of dicts with: day_of_week, start_time, end_time,
        course_code, course_name, slot_type, venue
    """
    records: list[dict] = []

    # Find timetable table — VTOP uses id "timeTableStyle" or similar
    table = soup.find("table", {"id": re.compile(r"timeTable", re.I)})
    if not table:
        # Fallback: look for table with day-of-week content in first column
        tables = soup.find_all("table")
        for t in tables:
            rows = t.find_all("tr")
            if len(rows) >= 2:
                first_cells = [
                    td.get_text(strip=True).upper()
                    for td in rows[1].find_all("td")[:1]
                ]
                if first_cells and first_cells[0] in ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"):
                    table = t
                    break

    if not table:
        # Last resort: find table with "Theory" or "Lab" text content
        tables = soup.find_all("table")
        for t in tables:
            text = t.get_text()
            if ("Theory" in text or "Lab" in text) and any(
                day in text for day in ("MON", "TUE", "WED", "THU", "FRI")
            ):
                table = t
                break

    if not table:
        logger.warning("Timetable table not found in page.")
        return records

    rows = table.find_all("tr")
    if len(rows) < 2:
        logger.warning("Timetable table has insufficient rows.")
        return records

    # Extract time slots from header row
    header_cells = rows[0].find_all(["th", "td"])
    time_slots: list[tuple[str, str]] = []  # (start_time, end_time)
    for cell in header_cells[1:]:  # Skip first column (empty or "Day")
        text = cell.get_text(strip=True)
        # Match patterns like "08:00-08:50", "8:00 - 8:50", "0800-0850"
        time_match = re.search(r"(\d{1,2}[:.]\d{2})\s*[-–]\s*(\d{1,2}[:.]\d{2})", text)
        if time_match:
            start = time_match.group(1).replace(".", ":")
            end = time_match.group(2).replace(".", ":")
            # Normalize to HH:MM
            if len(start) == 4:
                start = "0" + start
            if len(end) == 4:
                end = "0" + end
            time_slots.append((start, end))
        else:
            time_slots.append(("", ""))

    # Parse each day row
    day_map = {
        "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
        "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday",
        "MONDAY": "Monday", "TUESDAY": "Tuesday", "WEDNESDAY": "Wednesday",
        "THURSDAY": "Thursday", "FRIDAY": "Friday", "SATURDAY": "Saturday",
        "SUNDAY": "Sunday",
    }

    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue

        day_text = cells[0].get_text(strip=True).upper()
        day_of_week = day_map.get(day_text)
        if not day_of_week:
            continue

        for col_idx, cell in enumerate(cells[1:]):
            cell_text = cell.get_text(separator="\n", strip=True)
            if not cell_text or cell_text == "-" or len(cell_text.strip()) < 3:
                continue

            # Determine time slot for this column
            if col_idx < len(time_slots):
                start_time, end_time = time_slots[col_idx]
            else:
                start_time, end_time = "", ""

            # Parse cell content — VTOP typically has: CourseCode-Name-Type-Venue
            # Or multi-line: "BCSE302L\nData Structures\nTH\nSJT-404"
            parsed = _parse_timetable_cell(cell_text, cell)

            if parsed:
                records.append({
                    "day_of_week": day_of_week,
                    "start_time": start_time,
                    "end_time": end_time,
                    "course_code": parsed["course_code"],
                    "course_name": parsed["course_name"],
                    "slot_type": parsed["slot_type"],
                    "venue": parsed["venue"],
                })

    logger.info("Parsed %d timetable slots.", len(records))
    return records


def _parse_timetable_cell(cell_text: str, cell_element) -> dict | None:
    """Parse a single timetable cell into course info.

    Handles various VTOP formats:
    - Multi-line: "BCSE302L\\nData Structures\\nTH\\nSJT-404"
    - Dash-separated: "BCSE302L - Data Structures - TH - SJT-404"
    - Spans with different classes

    Returns:
        Dict with course_code, course_name, slot_type, venue, or None if empty.
    """
    # Try to extract from nested elements first (spans, divs)
    spans = cell_element.find_all(["span", "div", "p"])
    parts: list[str] = []
    if spans:
        parts = [s.get_text(strip=True) for s in spans if s.get_text(strip=True)]

    # Fallback to line-split
    if len(parts) < 2:
        # Split by newline or " - "
        parts = [p.strip() for p in re.split(r"[\n\r]+|(?:\s*-\s*){2,}", cell_text) if p.strip()]

    if not parts:
        return None

    # Extract course code (pattern: letters + digits, e.g. BCSE302L, BECE301L)
    course_code = ""
    course_name = ""
    slot_type = "theory"
    venue = ""

    for part in parts:
        if not course_code and re.match(r"^[A-Z]{2,5}\d{3,4}[A-Z]?$", part):
            course_code = part
        elif part.upper() in ("TH", "THEORY", "ETH"):
            slot_type = "theory"
        elif part.upper() in ("LO", "LAB", "ELA", "SS"):
            slot_type = "lab"
        elif re.match(r"^[A-Z]{2,4}[-\s]?\d{1,4}[A-Z]?$", part) and not course_code:
            # Could be venue like "SJT-404" — check if we already have a code
            venue = part
        elif re.match(r"^[A-Z]{2,5}[-\s]?\d{1,4}", part) and course_code:
            # Likely a venue
            venue = part
        elif not course_name and len(part) > 3 and not re.match(r"^[A-Z]{1,5}[-\s]?\d", part):
            course_name = part

    # If we didn't find a course code, this cell is probably not a class
    if not course_code:
        # One more attempt: find code-like pattern in full text
        code_match = re.search(r"\b([A-Z]{2,5}\d{3,4}[A-Z]?)\b", cell_text)
        if code_match:
            course_code = code_match.group(1)
        else:
            return None

    # Clean up course name
    if not course_name:
        # Remove known parts and use remainder as name
        remaining = cell_text
        for p in [course_code, venue, "TH", "LO", "LAB", "ETH", "ELA", "SS", "THEORY"]:
            remaining = remaining.replace(p, "")
        remaining = re.sub(r"[\n\r\-]+", " ", remaining).strip()
        if remaining and len(remaining) > 2:
            course_name = remaining
        else:
            course_name = course_code  # Fallback

    return {
        "course_code": course_code,
        "course_name": course_name.strip(),
        "slot_type": slot_type,
        "venue": venue,
    }


def _parse_float(value: str) -> float | None:
    """Safely parse a float from a table cell."""
    if not value or value in ("-", "N/A", "AB", ""):
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None

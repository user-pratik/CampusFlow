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

    Returns:
        Dict with: cgpa (float), total_credits (int)
    """
    result = {"cgpa": 0.0, "total_credits": 0}

    # Look for CGPA in the page text
    text = soup.get_text()

    cgpa_match = re.search(r"CGPA[:\s]*(\d+\.?\d*)", text, re.I)
    if cgpa_match:
        result["cgpa"] = float(cgpa_match.group(1))

    credits_match = re.search(r"(?:Total\s+)?Credits?\s*(?:Earned)?[:\s]*(\d+)", text, re.I)
    if credits_match:
        result["total_credits"] = int(credits_match.group(1))

    # Fallback: look in tables
    if result["cgpa"] == 0.0:
        tables = soup.find_all("table")
        for table in tables:
            for row in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                for i, cell in enumerate(cells):
                    if "cgpa" in cell.lower() and i + 1 < len(cells):
                        try:
                            result["cgpa"] = float(cells[i + 1])
                        except ValueError:
                            pass
                    if "credit" in cell.lower() and i + 1 < len(cells):
                        try:
                            result["total_credits"] = int(cells[i + 1])
                        except ValueError:
                            pass

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


def _parse_float(value: str) -> float | None:
    """Safely parse a float from a table cell."""
    if not value or value in ("-", "N/A", "AB", ""):
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None

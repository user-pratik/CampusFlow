"""VTOP sync worker — runs the Playwright scraper in its own process.

Usage:
    python vtop_sync_worker.py [semester_id]

If semester_id is provided, uses that. Otherwise picks the latest semester.
Outputs JSON summary on the last line of stdout.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from app.connectors.vtop.browser_scraper import VTOPBrowserScraper
from app.connectors.vtop.connector import VTOPConnector


async def main():
    semester_id = sys.argv[1] if len(sys.argv) > 1 else None

    scraper = VTOPBrowserScraper()

    if not await scraper.start():
        print(json.dumps({"success": False, "error": "Session expired. Run vtop_login_browser.py"}))
        return

    # Get semesters
    semesters = await scraper.get_semesters()

    if not semesters:
        print(json.dumps({"success": False, "error": "No semesters found"}))
        await scraper.close()
        return

    # Pick semester
    if semester_id and semester_id in semesters.values():
        sem_id = semester_id
        sem_name = [k for k, v in semesters.items() if v == semester_id][0]
    else:
        sem_name = list(semesters.keys())[0]
        sem_id = semesters[sem_name]

    await scraper.close()

    # Now run the full connector with the chosen semester
    connector = VTOPConnector()
    connector._semester_id = sem_id
    connector._semester_name = sem_name
    summary = await connector.run()
    print(json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main())

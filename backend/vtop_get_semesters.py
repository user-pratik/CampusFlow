"""Fetch available semesters from VTOP. Outputs JSON on last line."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from app.connectors.vtop.browser_scraper import VTOPBrowserScraper


async def main():
    scraper = VTOPBrowserScraper()
    if not await scraper.start():
        print(json.dumps({}))
        return

    semesters = await scraper.get_semesters()
    await scraper.close()
    print(json.dumps(semesters))


if __name__ == "__main__":
    asyncio.run(main())

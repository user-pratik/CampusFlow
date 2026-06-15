"""Test marks scraping with different content types."""
import asyncio
import httpx
from bs4 import BeautifulSoup
from app.connectors.vtop.session_store import SessionStore


async def main():
    store = SessionStore()
    cookies = await store.get_cookies_as_httpx()
    if not cookies:
        print("No session!")
        return

    client = httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False, cookies=cookies)

    # Get CSRF
    r = await client.get("https://vtopcc.vit.ac.in/vtop/content")
    soup = BeautifulSoup(r.text, "lxml")
    csrf = ""
    tag = soup.find("input", {"name": "_csrf"})
    if tag:
        csrf = tag.get("value", "")
    if not csrf:
        meta = soup.find("meta", {"name": "_csrf"})
        if meta:
            csrf = meta.get("content", "")
    auth_tag = soup.find("input", {"id": "authorizedIDX"})
    auth_id = auth_tag["value"] if auth_tag else "23BAI1126"
    print(f"CSRF: {csrf[:20]}, Auth: {auth_id}")

    # Try 1: Standard form POST (what we currently do)
    r1 = await client.post(
        "https://vtopcc.vit.ac.in/vtop/examinations/doStudentMarkView",
        data={
            "semesterSubId": "CH20252605",
            "authorizedID": auth_id,
            "_csrf": csrf,
        },
    )
    print(f"\nTry 1 (form data): {r1.status_code}, {len(r1.text)} chars")
    has_table = "fixedTableContainer" in r1.text or "<table" in r1.text[:5000]
    print(f"  Has table: {has_table}")

    # Try 2: Multipart form data (mimics FormData)
    r2 = await client.post(
        "https://vtopcc.vit.ac.in/vtop/examinations/doStudentMarkView",
        files={
            "semesterSubId": (None, "CH20252605"),
            "authorizedID": (None, auth_id),
            "_csrf": (None, csrf),
        },
    )
    print(f"\nTry 2 (multipart): {r2.status_code}, {len(r2.text)} chars")
    has_table2 = "fixedTableContainer" in r2.text or "<table" in r2.text[:5000]
    print(f"  Has table: {has_table2}")
    if has_table2:
        print("  FOUND MARKS TABLE!")
        # Save for parser testing
        with open("debug_marks_multipart.html", "w", encoding="utf-8") as f:
            f.write(r2.text)
        print(f"  Saved to debug_marks_multipart.html")

    await client.aclose()


asyncio.run(main())

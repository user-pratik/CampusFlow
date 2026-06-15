"""Find the marks data endpoint from the saved marks page HTML."""
from pathlib import Path
import re

# Read the FULL marks page (from the earlier save that was 30652 chars)
# Actually let me re-download it directly
import httpx
from sqlmodel import Session, select, create_engine
from app.models import EmailNotification
from app.connectors.vtop.session_store import SessionStore
from app.database import async_session_maker
import asyncio

async def main():
    store = SessionStore()
    cookies = await store.get_cookies_as_httpx()
    if not cookies:
        print("No session!")
        return
    
    client = httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False, cookies=cookies)
    
    # Get content page for CSRF
    r = await client.get("https://vtopcc.vit.ac.in/vtop/content")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "lxml")
    csrf = ""
    tag = soup.find("input", {"name": "_csrf"})
    if tag: csrf = tag.get("value", "")
    if not csrf:
        meta = soup.find("meta", {"name": "_csrf"})
        if meta: csrf = meta.get("content", "")
    
    auth_tag = soup.find("input", {"id": "authorizedIDX"})
    auth_id = auth_tag["value"] if auth_tag else "23BAI1126"
    
    print(f"CSRF: {csrf[:20]}, AuthID: {auth_id}")
    
    # Get the marks page shell
    r2 = await client.post("https://vtopcc.vit.ac.in/vtop/examinations/doStudentMarkView", data={
        "semesterSubId": "CH20252601",
        "authorizedID": auth_id,
        "_csrf": csrf,
    })
    print(f"\nPage shell: {r2.status_code}, {len(r2.text)} chars")
    
    # Find all onchange/submitTo patterns
    text = r2.text
    functions = re.findall(r"onchange=\"([^\"]+)\"", text)
    print(f"onchange functions: {functions}")
    
    submits = re.findall(r"submitTo:\s*\{url:\s*\"([^\"]+)\"", text)
    print(f"submitTo URLs: {submits}")
    
    # Find the doView function
    idx = text.find("doViewExamMark")
    if idx >= 0:
        print(f"\ndoViewExamMark context:")
        print(text[idx:idx+500])
    else:
        # Try other patterns
        idx2 = text.find("Exam")
        if idx2 >= 0:
            print(f"\nExam reference:")
            print(text[max(0,idx2-50):idx2+200])

asyncio.run(main())

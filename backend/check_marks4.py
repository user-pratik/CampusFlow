"""Find doViewExamMark function body."""
from pathlib import Path
import re
import httpx
from app.connectors.vtop.session_store import SessionStore
import asyncio

async def main():
    store = SessionStore()
    cookies = await store.get_cookies_as_httpx()
    client = httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False, cookies=cookies)
    r = await client.get("https://vtopcc.vit.ac.in/vtop/content")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "lxml")
    csrf = ""
    tag = soup.find("input", {"name": "_csrf"})
    if tag: csrf = tag.get("value", "")
    auth_tag = soup.find("input", {"id": "authorizedIDX"})
    auth_id = auth_tag["value"] if auth_tag else "23BAI1126"
    
    r2 = await client.post("https://vtopcc.vit.ac.in/vtop/examinations/doStudentMarkView", data={
        "semesterSubId": "CH20252601",
        "authorizedID": auth_id,
        "_csrf": csrf,
    })
    
    text = r2.text
    idx = text.find("function doViewExamMark")
    if idx >= 0:
        print("FOUND function doViewExamMark:")
        print(text[idx:idx+800])
    else:
        # Maybe it's inline or different name
        idx2 = text.find("doViewExamMark")
        while idx2 >= 0:
            context = text[max(0,idx2-20):idx2+100]
            if "function" in context or "url" in context:
                print(f"Ref at {idx2}:", context)
            idx2 = text.find("doViewExamMark", idx2+1)
            if idx2 > 0 and text[idx2-20:idx2].find("function") >= 0:
                print("\nFUNCTION FOUND:")
                print(text[idx2-20:idx2+600])
                break

asyncio.run(main())

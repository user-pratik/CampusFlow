from pathlib import Path
from bs4 import BeautifulSoup

html = Path("debug_marks_multipart.html").read_text(encoding="utf-8")
soup = BeautifulSoup(html, "lxml")

table = soup.find("table", id="fixedTableContainer")
if table:
    rows = table.find_all("tr")
    print(f"Table fixedTableContainer: {len(rows)} rows")
    for i, row in enumerate(rows[:3]):
        cells = [td.get_text(strip=True)[:30] for td in row.find_all("td")]
        print(f"  Row {i} ({len(cells)} cells): {cells[:8]}")
else:
    print("fixedTableContainer not found")
    tables = soup.find_all("table")
    print(f"Total tables: {len(tables)}")
    for i, t in enumerate(tables[:5]):
        tid = t.get("id", "no-id")
        rows = t.find_all("tr")
        print(f"  Table {i}: id={tid}, {len(rows)} rows")
        if rows:
            cells = [td.get_text(strip=True)[:20] for td in rows[0].find_all("td")]
            print(f"    First row: {cells[:6]}")

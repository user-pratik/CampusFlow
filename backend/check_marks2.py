from pathlib import Path
import re

html = Path("debug_marks.html").read_text(encoding="utf-8")

# Find all JS functions
funcs = re.findall(r"function\s+(\w+)", html)
print("Functions:", funcs[:15])

# Find any URL patterns
urls = re.findall(r"url\s*[:=]\s*['\"]([^'\"]+)['\"]", html)
print("\nURLs:", urls[:10])

# Find submitTo patterns
submits = re.findall(r"submitTo\s*:\s*\{([^}]+)\}", html)
print("\nSubmitTo:", submits[:5])

# Check if there's a semesterSubId select
if "semesterSubId" in html:
    idx = html.find("semesterSubId")
    print("\nsemesterSubId context:", html[idx:idx+200])

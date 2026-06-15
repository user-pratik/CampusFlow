from pathlib import Path
import re

html = Path("debug_marks.html").read_text(encoding="utf-8")
# Find the submit URL for marks
matches = re.findall(r'submitTo:\s*\{url:\s*"([^"]+)"', html)
print("Submit URLs:", matches[:5])

# Find the function name
idx = html.find("submitTo")
if idx >= 0:
    print("\nAround submitTo:")
    print(html[idx:idx+300])

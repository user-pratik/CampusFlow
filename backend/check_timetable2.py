from pathlib import Path
html = Path("debug_timetable.html").read_text(encoding="utf-8")
idx = html.find("function processViewTimeTable")
print(html[idx:idx+1000])

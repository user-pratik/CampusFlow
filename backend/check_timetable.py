"""Check timetable HTML structure."""
from pathlib import Path
import re

html = Path("debug_timetable.html").read_text(encoding="utf-8")

# Find processViewTimeTable function
idx = html.find("function processViewTimeTable")
if idx >= 0:
    print("FOUND function at", idx)
    print(html[idx:idx+500])
else:
    print("Function not found inline - checking for script sources")
    scripts = re.findall(r'<script[^>]*src="([^"]*)"', html)
    print("External scripts:", scripts[:10])
    
    # Find all AJAX-like URL patterns
    ajax_urls = re.findall(r"url\s*[:=]\s*['\"]([^'\"]+)['\"]", html)
    print("AJAX URLs:", ajax_urls[:10])
    
    # Find the form action
    forms = re.findall(r'<form[^>]*action="([^"]*)"', html)
    print("Form actions:", forms[:5])
    
    # Check if there's a script block with the function
    script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
    for i, block in enumerate(script_blocks):
        if 'TimeTable' in block or 'timetable' in block:
            print(f"\nScript block {i} has TimeTable reference:")
            print(block[:500])

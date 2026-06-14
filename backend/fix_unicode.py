"""Fix ALL problematic unicode in orchestrator.py"""
import re

with open('app/agents/orchestrator.py', 'rb') as f:
    content = f.read()

# Replace all common problematic unicode chars with ASCII equivalents
replacements = {
    b'\xe2\x80\x99': b"'",     # right single quote
    b'\xe2\x80\x98': b"'",     # left single quote
    b'\xe2\x80\x9c': b'"',     # left double quote
    b'\xe2\x80\x9d': b'"',     # right double quote
    b'\xe2\x80\x94': b'--',    # em dash
    b'\xe2\x80\x93': b'-',     # en dash
    b'\xe2\x86\x92': b'->',    # right arrow
}

for old, new in replacements.items():
    count = content.count(old)
    if count:
        print(f"Replacing {old!r} -> {new!r} ({count} occurrences)")
        content = content.replace(old, new)

with open('app/agents/orchestrator.py', 'wb') as f:
    f.write(content)

print("Done. All unicode chars replaced with ASCII.")

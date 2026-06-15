import httpx
import json

r = httpx.get("http://localhost:8000/api/timetable", timeout=10)
d = r.json()
print("Days:", list(d.keys()))
for day in list(d.keys())[:3]:
    classes = d[day]
    print(f"\n{day} ({len(classes)} classes):")
    for c in classes[:3]:
        print(f"  {c['start_time']}-{c['end_time']} | {c['course_code']} | {c['venue']} | {c['slot_type']}")

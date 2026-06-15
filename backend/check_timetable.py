import httpx, json
r = httpx.get('http://localhost:8000/api/timetable', timeout=10)
d = r.json()
print('Days:', list(d.keys()))
for day in list(d.keys())[:3]:
    classes = d[day]
    print(f'{day} ({len(classes)} classes):')
    for c in classes[:2]:
        print(f'  {c.get("start_time")}-{c.get("end_time")} | {c.get("course_code")} | {c.get("slot_type")}')

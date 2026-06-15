import httpx, json
r = httpx.get("http://localhost:8000/api/timetable", timeout=10)
d = r.json()
monday = d.get("Monday", [])
print(f"Monday classes: {len(monday)}")
print(json.dumps(monday, indent=2))

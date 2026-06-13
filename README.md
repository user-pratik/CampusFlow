# CampusFlow

A unified campus assistant that ingests WhatsApp messages, scrapes VTOP academic data, and generates AI-powered daily briefings.

---

## Quick Start (for teammates with credentials)

### Prerequisites

- Python 3.11+
- Node.js 18+
- Chrome/Chromium (Playwright will use it)

### 1. Clone and install backend

```bash
git clone <repo-url>
cd "Amazon Hackon 2026"

cd backend
python -m venv venv
.\venv\Scripts\activate        # Windows
pip install -r requirements.txt
playwright install chromium
```

### 2. Set up environment

```bash
copy .env.example .env
```

Edit `.env` with the real credentials:

```env
GROQ_API_KEY="gsk_key1,gsk_key2,gsk_key3"
GROQ_MODEL=llama-3.3-70b-versatile
VTOP_USERNAME=223BAI1126
VTOP_PASSWORD=<password>
VTOP_POLL_INTERVAL=1800
```

### 3. Login to VTOP (one-time — saves session for 8-12 hours)

```bash
python vtop_login_browser.py
```

A browser opens. Credentials are auto-filled. **You only solve the reCAPTCHA and click Login.** Once the dashboard loads, the session is saved to `vtop_session.json`.

### 4. Start the backend

```bash
python run.py
```

Server runs at `http://localhost:8000`. Health check: `GET /health`.

### 5. Sync VTOP data

Either:
- Call `POST http://localhost:8000/api/academic/sync` (from frontend or Postman)
- Or use the semester selector in the frontend and click "Load Data"

### 6. Install and start frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

---

## Testing the WhatsApp pipeline

Send a message to the webhook:

```bash
curl -X POST http://localhost:8000/api/webhooks/whatsapp ^
  -H "Content-Type: application/json" ^
  -d "{\"text\": \"URGENT: Submit Cloud Computing assignment by tomorrow 5 PM!\", \"group\": \"CSE Official 2026\"}"
```

---

## Architecture

```
backend/
├── app/
│   ├── main.py              ← FastAPI app + CORS + scheduler
│   ├── models.py            ← SQLModel tables (Notice, Task, Event, Digest, Attendance, CourseMark, AcademicProfile)
│   ├── database.py          ← Async SQLite engine
│   ├── scheduler.py         ← APScheduler (digest at 8AM, VTOP poll every 30min)
│   ├── agents/
│   │   ├── notice_agent.py  ← Groq LLM extraction
│   │   ├── scheduler_agent.py ← DB insert + conflict detection
│   │   └── digest_agent.py  ← Morning briefing generation
│   ├── connectors/vtop/
│   │   ├── browser_scraper.py ← Playwright + jQuery AJAX injection
│   │   └── connector.py     ← Orchestrates scrape → DB
│   ├── routers/             ← API endpoints
│   └── utils/
│       ├── llm_client.py    ← Rolling Groq key rotation
│       └── hashing.py       ← SHA-256 dedup
├── vtop_login_browser.py    ← One-time browser login script
├── vtop_sync_worker.py      ← Subprocess worker for Playwright sync
└── requirements.txt

frontend/
├── src/
│   ├── app/page.tsx         ← Main page
│   ├── components/
│   │   ├── ConflictAlert.tsx
│   │   ├── MorningBriefing.tsx
│   │   ├── AcademicDashboard.tsx ← CGPA + Attendance + Marks (expandable)
│   │   └── CampusFeed.tsx
│   └── lib/api.ts           ← Typed API client
└── .env.local               ← NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## If VTOP session expires

You'll see "Session expired" in logs or the sync returns `success: false`. Just re-run:

```bash
cd backend
python vtop_login_browser.py
```

Solve captcha again. Done.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Server health check |
| GET | /api/profile | User profile from JSON |
| GET | /api/notices | All notices |
| GET | /api/tasks | All tasks |
| GET | /api/digest/latest | Latest AI briefing |
| POST | /api/digest/trigger | Generate new briefing now |
| POST | /api/webhooks/whatsapp | WhatsApp message intake |
| GET | /api/academic/attendance | Attendance per course |
| GET | /api/academic/marks | All individual marks |
| GET | /api/academic/profile | CGPA + credits + overall attendance |
| GET | /api/academic/semesters | Available VTOP semesters |
| POST | /api/academic/sync | Trigger VTOP scrape (body: {semester_id}) |

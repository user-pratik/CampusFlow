# CampusFlow

An AI-powered campus assistant for VIT students. Aggregates academic data from VTOP, WhatsApp messages, and provides an intelligent chat interface with scheduling, reminders, and daily digests.

## Features

- **VTOP Integration** — Auto-scrapes attendance, marks, CGPA from VIT's student portal
- **WhatsApp Bridge** — Receives and processes WhatsApp group messages via Evolution API
- **AI Chat** — LLM-powered assistant (Groq/Llama) that understands your academic context
- **Daily Digest** — Morning briefing with schedule, pending tasks, and alerts
- **Smart Reminders** — AI-generated reminders from class messages and deadlines
- **Academic Dashboard** — Real-time attendance percentages and marks overview

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Next.js UI │────▶│ FastAPI Back │────▶│  Groq LLM API   │
│  (port 3000)│     │  (port 8000) │     │  (llama-3.3-70b)│
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  SQLite  │ │  VTOP    │ │ Evolution│
        │   (DB)   │ │ Scraper  │ │   API    │
        └──────────┘ │(Playwright)│ │(WhatsApp)│
                     └──────────┘ └──────────┘
```

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend |
| Node.js | 18+ | Frontend |
| Docker | Any | WhatsApp bridge (optional) |
| ngrok | Any | Public webhook URL (optional) |

## Quick Start (Windows)

```bash
git clone https://github.com/user-pratik/CampusFlow.git
cd CampusFlow
```

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (needed for VTOP scraping)
playwright install chromium

# Configure environment
copy .env.example .env
# Edit .env with your credentials (see Configuration below)

# Start the backend
python run.py
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment (optional — defaults to localhost:8000)
copy .env.example .env.local

# Start the dev server
npm run dev
```

### 3. Open the App

Navigate to **http://localhost:3000**

### One-Click Start (after initial setup)

Double-click `start.bat` in the project root — it starts backend, frontend, and WhatsApp bridge together.

## Configuration

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Your Groq API key ([get one free](https://console.groq.com/keys)) |
| `GROQ_MODEL` | No | Model name (default: `llama-3.3-70b-versatile`) |
| `VTOP_USERNAME` | Yes | Your VIT registration number |
| `VTOP_PASSWORD` | Yes | Your VTOP portal password |
| `VTOP_POLL_INTERVAL` | No | Seconds between auto-syncs (default: `1800` = 30 min) |
| `NGROK_AUTHTOKEN` | Optional | For WhatsApp webhooks ([get free token](https://dashboard.ngrok.com)) |
| `EVOLUTION_API_KEY` | No | Evolution API key (default: `campusflow-secret`) |
| `EVOLUTION_BASE_URL` | No | Evolution API URL (default: `http://localhost:8080`) |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | No | Backend URL (default: `http://localhost:8000`) |

## VTOP Login

CampusFlow uses Playwright to scrape your academic data from VTOP. On first run:

1. Click **Sync** in the sidebar
2. A Chromium browser window opens with the VTOP login page
3. Enter your credentials and solve the reCAPTCHA
4. Click Login — session cookies are saved automatically
5. The browser closes and data syncs in the background

Session cookies are reused until they expire. When they expire, clicking Sync opens the login browser again.

## WhatsApp Integration (Optional)

WhatsApp support requires Docker for the Evolution API container:

```bash
# From project root
docker compose up -d
```

On backend startup, it will:
1. Start an ngrok tunnel (needs `NGROK_AUTHTOKEN`)
2. Create a WhatsApp instance
3. Generate a QR code (`backend/whatsapp_qr.html`)
4. Open that file and scan with WhatsApp → Linked Devices → Link a Device

## Testing the WhatsApp Pipeline

Send a test message to the webhook:

```bash
curl -X POST http://localhost:8000/api/webhooks/whatsapp ^
  -H "Content-Type: application/json" ^
  -d "{\"text\": \"URGENT: Submit Cloud Computing assignment by tomorrow 5 PM!\", \"group\": \"CSE Official 2026\"}"
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Server health check |
| GET | /api/status | Service status (ngrok, WhatsApp, VTOP) |
| GET | /api/profile | User profile from JSON |
| GET | /api/notices | All notices |
| GET | /api/tasks | All tasks |
| GET | /api/digest/latest | Latest AI briefing |
| POST | /api/digest/trigger | Generate new briefing now |
| POST | /api/webhooks/whatsapp | WhatsApp message intake |
| POST | /api/chat | Chat with AI assistant |
| GET | /api/academic/attendance | Attendance per course |
| GET | /api/academic/marks | All individual marks |
| GET | /api/academic/profile | CGPA + credits + overall attendance |
| GET | /api/academic/semesters | Available VTOP semesters |
| POST | /api/academic/sync | Trigger VTOP scrape (body: {semester_id}) |
| POST | /api/academic/login | Manually open VTOP login browser |
| POST | /api/academic/full-sync | One-button: login + sync + WhatsApp QR |

## Project Structure

```
CampusFlow/
├── backend/
│   ├── app/
│   │   ├── agents/          # LLM agents (orchestrator, academic, digest, etc.)
│   │   ├── connectors/      # External service connectors (VTOP, WhatsApp)
│   │   ├── routers/         # FastAPI route handlers
│   │   ├── schemas/         # Pydantic/extraction schemas
│   │   ├── utils/           # LLM client, hashing, user context
│   │   ├── database.py      # SQLModel + async SQLite
│   │   ├── main.py          # FastAPI app entry point
│   │   ├── scheduler.py     # APScheduler (digest + VTOP poll)
│   │   └── startup.py       # Boot orchestrator (ngrok, WhatsApp, VTOP)
│   ├── data/                # Runtime data (actions, memory, fabricated)
│   ├── tests/               # Pytest test suite
│   ├── .env.example         # Environment template
│   ├── requirements.txt     # Python dependencies
│   └── run.py               # Dev server entry point
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js app router pages
│   │   ├── components/      # React components (Chat, Sidebar, panels)
│   │   └── lib/             # API client, types, utilities
│   ├── .env.example         # Frontend env template
│   └── package.json         # Node dependencies
├── docker-compose.yml       # Evolution API (WhatsApp bridge)
├── start.bat                # One-click launcher (Windows)
├── start.ps1                # PowerShell startup script
└── README.md
```

## Running Tests

```bash
cd backend
venv\Scripts\activate
pytest
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| VTOP sync fails | Session expired — click Sync to re-login |
| WhatsApp not connecting | Ensure Docker is running: `docker compose up -d` |
| ngrok error | Set `NGROK_AUTHTOKEN` in `.env` or run `ngrok http 8000` manually |
| Playwright not found | Run `playwright install chromium` in the backend venv |
| Backend won't start | Check `.env` exists and has valid `GROQ_API_KEY` |
| Frontend can't reach backend | Ensure backend is running on port 8000 |

## Tech Stack

- **Frontend**: Next.js 16, React 19, Tailwind CSS 4, TypeScript
- **Backend**: FastAPI, SQLModel, async SQLite, APScheduler
- **AI**: Groq API (Llama 3.3 70B)
- **Scraping**: Playwright (headless Chromium)
- **WhatsApp**: Evolution API (Docker)
- **Tunneling**: ngrok (pyngrok)

## License

MIT

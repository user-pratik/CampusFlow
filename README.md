# CampusFlow

A personal AI-powered campus assistant for VIT Chennai students.

## Features

- **VTOP Sync** — Auto-fetch attendance, marks, CGPA via Playwright login
- **Gmail Integration** — Reads college emails, classifies into EXAM/PLACEMENT/FEE/EVENT
- **Google Calendar Agent** — Chat to add events directly to your calendar
- **AI Chat** — Ask anything about your emails, attendance, marks

## Stack

- Backend: FastAPI + SQLModel + Playwright
- Frontend: Next.js 16 + Tailwind CSS
- AI: Groq (free tier) + rule-based email classifier

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Google Cloud project with Gmail + Calendar API enabled

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
python run.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## First Run

1. Open http://localhost:3000
2. Click **Sync** → login with VTOP credentials (Playwright browser opens)
3. Click **Email** → Connect Gmail → authorize
4. Start chatting!

## Secrets Required

| File | Purpose |
|------|---------|
| `backend/credentials.json` | Google OAuth client (download from Cloud Console) |
| `backend/.env` | API keys (Groq, OpenRouter) |

> **Note:** `credentials.json`, `gmail_token.json`, `vtop_session.json`, and `.env` are gitignored and must be created locally.

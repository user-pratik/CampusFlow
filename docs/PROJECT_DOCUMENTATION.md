# CampusFlow — Project Documentation

> **AI-Powered Unified Operating System for Student Life at VIT Chennai**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Solution Architecture](#3-solution-architecture)
4. [Features (Detailed)](#4-features-detailed)
5. [Technical Implementation](#5-technical-implementation)
6. [API Endpoints](#6-api-endpoints)
7. [Setup & Installation](#7-setup--installation)
8. [Innovation & Differentiators](#8-innovation--differentiators)
9. [Future Roadmap](#9-future-roadmap)
10. [Team](#10-team)

---

## 1. Executive Summary

### The Problem

Student life at VIT Chennai is fragmented across disconnected digital platforms. Academic data lives on VTOP (with no mobile interface or push notifications), university updates are scattered across 10+ WhatsApp groups, important emails drown in Gmail noise, and calendar management is entirely manual. Students spend hours each week context-switching between platforms just to stay informed.

### The Solution

**CampusFlow** is a unified AI operating system for student life. It brings together VTOP academics, WhatsApp group intelligence, Gmail classification, Google Calendar automation, and a conversational AI agent into a single, cohesive desktop-style interface. CampusFlow doesn't just aggregate — it *understands*. Its multi-agent AI pipeline classifies, prioritizes, and surfaces actionable intelligence so students can focus on what matters.

### Target Audience

VIT Chennai undergraduate students (immediately applicable), with architecture designed for expansion to other universities and institutions.

### Hackathon Theme

**AI for Campus, Community & Everyday Life** — CampusFlow directly addresses the daily pain points of campus life through intelligent automation, real-time data aggregation, and AI-driven decision support.

---

## 2. Problem Statement

| Pain Point | Current State | Impact |
|---|---|---|
| VTOP Portal | No notifications, no mobile UI, clunky web-only interface | Students miss deadline changes, attendance drops below 75% unknowingly |
| WhatsApp Groups | 37+ groups (batch, course, club, placement) | Critical notices buried under memes and spam |
| Gmail Overload | Mix of placement, academic, fee, event emails | Important deadlines missed, no categorization |
| Calendar | Fully manual entry, no connection to VTOP | Double-booked slots, forgotten exams |
| No Unified View | Each platform requires separate login/check | 30+ min/day wasted on context-switching |
| Attendance Tracking | Check VTOP manually per course | Students realize they're below 75% too late |
| Marks & GPA | Hidden behind multiple VTOP clicks | No "what-if" projection or early warning |

### Core Challenges Addressed

1. **Information Fragmentation** — No single source of truth for a student's academic + social + administrative life
2. **Zero Proactive Intelligence** — Existing systems are passive; they don't warn, predict, or recommend
3. **Manual Drudgery** — Calendar events, deadline tracking, and attendance math are done by hand
4. **Platform Lock-in** — VTOP's proprietary session management makes automation difficult (solved via CDP cookie capture)

---

## 3. Solution Architecture

### 3.1 System Overview

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | FastAPI + SQLModel + SQLite | REST API, async processing, lightweight persistence |
| **Frontend** | Next.js 15 + Tailwind CSS + shadcn/ui | Desktop-OS-style interface with window manager |
| **AI Engine** | Groq (llama-3.3-70b-versatile) | Intent classification, NLP extraction, conversational AI |
| **VTOP Integration** | httpx + BeautifulSoup + CDP | Cookie-based scraping, HTML parsing |
| **Gmail Integration** | Google OAuth2 + Gmail API + Calendar API | Email sync, classification, event creation |
| **WhatsApp** | n8n + UltraMsg webhook pipeline | Real-time group message ingestion |
| **Database** | SQLite (via aiosqlite + SQLModel) | Zero-config, file-based, production-ready for single-user |

### 3.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMPUSFLOW ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌───────────┐  │
│  │   VTOP      │    │   Gmail     │    │  WhatsApp    │    │  Google   │  │
│  │  (httpx +   │    │  (OAuth2 +  │    │  (n8n +      │    │ Calendar  │  │
│  │   CDP)      │    │  Gmail API) │    │  UltraMsg)   │    │   API     │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬───────┘    └─────┬─────┘  │
│         │                  │                   │                   │        │
│         ▼                  ▼                   ▼                   ▼        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     FASTAPI BACKEND (Async)                          │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │
│  │  │ Routers  │  │Connectors│  │  Agents  │  │   Database       │   │   │
│  │  │(REST API)│  │(Scrapers)│  │(AI Logic)│  │  (SQLite/SQLModel)│   │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    AI AGENT ORCHESTRATION LAYER                       │   │
│  │                                                                       │   │
│  │  ┌────────────┐  ┌─────────────────┐  ┌───────────────────────┐    │   │
│  │  │Orchestrator│─▶│Workflow Planner  │─▶│ Specialist Agents     │    │   │
│  │  │  (Router)  │  │(Intent+DataReq) │  │ (Academic, Schedule,  │    │   │
│  │  └────────────┘  └─────────────────┘  │  Attendance, GPA,     │    │   │
│  │                                        │  Connector, Placement)│    │   │
│  │                                        └───────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   NEXT.JS 15 FRONTEND (Desktop OS UI)                │   │
│  │                                                                       │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │
│  │  │  Agent   │  │  Window  │  │   App    │  │  Notification    │   │   │
│  │  │  Shell   │  │ Manager  │  │   Grid   │  │    Center        │   │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Features (Detailed)

### 4.1 VTOP Integration

**Technology**: httpx (HTTP client) + BeautifulSoup (HTML parsing) + Chrome DevTools Protocol (CDP) cookie capture

#### How It Works

1. **Session Capture** — User logs into VTOP via an embedded browser frame. CampusFlow captures session cookies through CDP (Chrome DevTools Protocol), storing them encrypted in the `vtop_sessions` table.
2. **HTTP Scraping** — Using stored cookies and CSRF tokens, the `SyncOrchestrator` makes direct HTTP POST requests to VTOP endpoints (no browser needed after login).
3. **HTML Parsing** — `scrapers.py` contains dedicated parsers:
   - `parse_attendance()` — Extracts course-wise attendance (code, title, attended, total, percentage)
   - `parse_marks()` — Two-step scraper: first gets course list, then per-course marks detail
   - `parse_timetable()` — Extracts VIT slot codes and maps them to days/times
   - `parse_academic_history()` — Extracts CGPA, total credits, semester info

#### VIT Slot Mapping System

CampusFlow includes a comprehensive mapping of 50+ VIT slot codes to actual days and times:

```python
VIT_PERIOD_TIMES = {
    1:  ("08:00", "08:50"),   2:  ("09:00", "09:50"),
    3:  ("10:00", "10:50"),   4:  ("11:00", "11:50"),
    5:  ("12:00", "12:50"),   6:  ("14:00", "14:50"),
    7:  ("15:00", "15:50"),   8:  ("16:00", "16:50"),
    9:  ("17:00", "17:50"),   10: ("18:00", "18:50"),
    11: ("19:00", "19:50"),
}
```

| Slot Type | Examples | Pattern |
|---|---|---|
| Morning Theory | A1, B1, C1, D1, E1, F1, G1 | 2-3 periods, 3-5 days/week |
| Afternoon Theory | A2, B2, C2, D2, E2, F2, G2 | 1-2 periods, 3-5 days/week |
| Tutorial | TA1, TB1, TC1, TD1, TE1, TF1, TG1 | Single period, follows parent slot days |
| Lab | L1–L50 | 2-period blocks, single day |

Combined slots like `"A2+TA2"` are split and resolved independently, with deduplication.

---

### 4.2 Gmail Intelligence

**Technology**: Google OAuth2 + Gmail API + Rule-based Classifier

#### Email Classification Categories

| Category | Priority | Triggers |
|---|---|---|
| **PLACEMENT** | High | Company names, CTC, "hiring", "drive", placement cell sender |
| **EXAM** | High | "CAT", "FAT", "exam schedule", "seating", "hall ticket" |
| **FEE** | High | "fee payment", "dues", "hostel fee", "last date" |
| **EVENT** | Normal | "hackathon", "workshop", "webinar", "fest" |
| **ANNOUNCEMENT** | Normal | Dean's office, VIT official, academic announcements |
| **GENERAL** | Low | Everything else (newsletters, promotions, etc.) |

#### Features
- **OAuth2 Flow** — Browser-based consent, token stored locally
- **Batch Sync** — Fetches last 50 emails, classifies, deduplicates by `gmail_msg_id`
- **Real-time Reclassification** — Every read re-applies current classifier rules (no stale categories)
- **Deadline Extraction** — LLM parses classified emails to extract dates, creating `Deadline` records

---

### 4.3 WhatsApp Integration

**Technology**: n8n workflow automation + UltraMsg API + webhook pipeline

#### Architecture
- **37 WhatsApp groups** monitored via UltraMsg connected to n8n
- **n8n Workflow** → HTTP POST to `/api/webhooks/whatsapp-n8n`
- **Deduplication** — MD5 hash of `sender + timestamp + message[:50]`
- **Classification** — Same classifier as Gmail applied to WhatsApp messages
- **Storage** — Messages stored as `EmailNotification` with sender prefix `"WhatsApp: {group_name}"`

#### Pipeline Flow
```
WhatsApp Group → UltraMsg → n8n Workflow → POST /api/webhooks/whatsapp-n8n
                                                    ↓
                                          classify_email(subject, sender, body)
                                                    ↓
                                          Store in email_notifications table
                                          (sender = "WhatsApp: GroupName")
```

The original Evolution API webhook (`/api/webhooks/whatsapp`) also supports direct payloads with a full NoticeAgent → SchedulerAgent pipeline for structured extraction.

---

### 4.4 Google Calendar Integration

**Technology**: Google Calendar API v3 + Natural Language Processing

#### Capabilities
- **Create Events** — Natural language → structured event (title, date, time, location, duration)
- **List Upcoming** — Fetches next 15 events from primary calendar
- **Timezone Aware** — All events created in `Asia/Kolkata`
- **AI-Triggered** — The orchestrator can create calendar events from chat ("remind me about X on Friday at 3pm")

```python
# Calendar event creation interface
create_calendar_event(
    title: str,        # "CAT 2 - Data Structures"
    date: str,         # "2025-01-20"
    time: str,         # "14:00"
    description: str,  # Optional details
    location: str,     # "SJT 401"
    duration_hours: int # Default: 1
)
```

---

### 4.5 AI Chat (Multi-Agent Orchestration)

**Technology**: Groq API (llama-3.3-70b-versatile) + Multi-agent routing + Conversation memory

#### Agent Architecture

The system uses a two-tier routing architecture:

1. **OrchestratorAgent** — Intent classifier that routes to specialist agents
2. **WorkflowPlanner** — LLM-driven planner that combines routing + data retrieval in one step

#### Intent Classification (Router Prompt)

The router classifies user messages into:
- `academic` — Marks, grades, CGPA, GPA projection
- `attendance_risk` — Attendance %, skip calculations
- `schedule` — Study plan creation
- `action` — Alarms, reminders, actionable tasks
- `connector` — WhatsApp/email/timetable/deadlines queries
- `general` — Greetings, vague queries, multi-topic

#### Specialist Agents

| Agent | Responsibility |
|---|---|
| `AcademicAgent` | Marks analysis, GPA projection, grade requirements |
| `AttendanceRiskAgent` | Per-course risk, 75% threshold, skip calculations |
| `ScheduleAgent` | Study plan generation, time management |
| `ActionAgent` | Alarm/reminder/task creation and tracking |
| `ConnectorAgent` | Email/WhatsApp/timetable/deadline queries |
| `GPAProjectionAgent` | What-if CGPA analysis, target grade computation |
| `PlacementPrepAgent` | Drive extraction, eligibility check, prep checklists |
| `DeadlineAggregator` | Cross-source deadline extraction and timeline |
| `DigestAgent` | Daily summary generation |
| `NoticeAgent` | WhatsApp message parsing and structured extraction |

#### Keyword Overrides & Anti-Hallucination

The planner includes explicit negative examples:
- "how much more attendance do I need to get over 50%" → `attendance_risk` (NOT gpa)
- "do I need 75%" → `regulations` (policy question, NOT attendance calculator)
- "how am I doing" → `chat` (too vague for any specific agent)

#### Conversation Memory

Multi-turn conversations are maintained per `session_id`, allowing contextual follow-ups without re-explaining context.

---

### 4.6 Timetable & Free Slot Detection

**Technology**: VIT slot code resolution + gap analysis algorithm

#### How It Works

1. VTOP stores timetable as slot codes (e.g., `"A2+TA2"`, `"L31+L32"`)
2. CampusFlow resolves each slot code to actual day(s) and time(s) using `VIT_SLOT_TIMING`
3. Overlapping/adjacent periods are merged
4. Free gaps between classes are computed within the 08:00–20:00 window

#### VIT Period Times (Full Day)

| Period | Time |
|---|---|
| 1 | 08:00 – 08:50 |
| 2 | 09:00 – 09:50 |
| 3 | 10:00 – 10:50 |
| 4 | 11:00 – 11:50 |
| 5 | 12:00 – 12:50 |
| 6 | 14:00 – 14:50 |
| 7 | 15:00 – 15:50 |
| 8 | 16:00 – 16:50 |
| 9 | 17:00 – 17:50 |
| 10 | 18:00 – 18:50 |
| 11 | 19:00 – 19:50 |

#### Free Slot Algorithm
```
Input: day_classes sorted by start_time, window (08:00–20:00)
1. Merge overlapping occupied intervals
2. Walk from window_start, find gaps before each occupied block
3. Add trailing gap from last class to window_end
Output: [{start_time, end_time, duration_minutes}]
```

---

### 4.7 Attendance Intelligence

**Technology**: Risk calculation engine + VIT academic regulation awareness

#### 75% Rule Implementation
- VIT requires minimum 75% attendance for exam eligibility
- **9.0+ CGPA Exemption**: Students with CGPA ≥ 9.0 and no backlogs are exempt from the 75% rule
- CampusFlow's student profile (`CGPA: 9.11, No backlogs`) is factored into all attendance responses

#### Risk Levels

| Level | Condition | Action |
|---|---|---|
| **Critical** | < 75% currently | "Cannot skip any more classes" |
| **Warning** | 75%–80% | "Can skip X more before dropping below threshold" |
| **Safe** | > 80% | "Can safely skip Y classes" |

#### Per-Course Risk Calculation
```python
calculate_risk(
    course_code: str,      # "BCSE305L"
    course_title: str,     # "Data Structures"
    attended: int,         # 28
    total: int,            # 35
)
# Returns: risk_level, classes_can_skip, percentage, recommendation
```

---

### 4.8 Marks & GPA Intelligence

**Technology**: Two-step VTOP scraper + grade-point projection engine

#### Marks Data Model
Each mark entry captures:
- `course_code` / `course_title` — Course identification
- `mark_title` — Assessment name (e.g., "CAT 1", "Assessment - 1", "Final Assessment Test")
- `max_mark` / `score` — Raw marks
- `weightage_pct` / `weightage_mark` — Weighted contribution
- `status` — "Present" / "Absent"

#### GPA Projection Features

1. **Single-Course Projection** — "If I get an A in BCSE302L, what's my new CGPA?"
2. **Target CGPA** — "What grades do I need to reach 9.5?"
3. **What-If Analysis** — Explore grade scenarios across multiple courses

#### Grade Point Scale (VIT)

| Grade | Points |
|---|---|
| S | 10 |
| A | 9 |
| B | 8 |
| C | 7 |
| D | 6 |
| E | 5 |
| F | 0 |

---

## 5. Technical Implementation

### 5.1 Agent Architecture Tree

```
OrchestratorAgent (Central Brain)
├── WorkflowPlanner (LLM-driven intent + data routing)
├── AcademicAgent (marks, grades, regulations)
├── AttendanceRiskAgent (75% rule, skip calculator)
├── ScheduleAgent (study plans, time management)
├── ActionAgent (alarms, reminders, task tracking)
├── ConnectorAgent (email, WhatsApp, timetable, deadlines)
├── GPAProjectionAgent (CGPA what-if, target grades)
├── PlacementPrepAgent (drive extraction, eligibility)
├── DeadlineAggregator (cross-source deadline sync)
├── DigestAgent (daily summary)
├── NoticeAgent (WhatsApp → structured extraction)
├── SchedulerAgent (conflict detection, DB persistence)
└── ConversationMemory (multi-turn context)
```

### 5.2 Data Flow

```
┌──────────┐     ┌──────────┐     ┌───────────────┐     ┌──────────────┐
│  User    │────▶│ Frontend │────▶│ POST /api/chat│────▶│ Orchestrator │
│  Input   │     │ (Next.js)│     │               │     │              │
└──────────┘     └──────────┘     └───────────────┘     └──────┬───────┘
                                                                │
                                                    ┌───────────┼───────────┐
                                                    ▼           ▼           ▼
                                              ┌──────────┐┌──────────┐┌──────────┐
                                              │ Classify ││ Gather   ││ Route to │
                                              │ Intent   ││ Context  ││ Agent    │
                                              └──────────┘└──────────┘└──────────┘
                                                                                │
                                                                                ▼
                                                                      ┌──────────────┐
                                                                      │ Specialist   │
                                                                      │ Agent Reply  │
                                                                      └──────┬───────┘
                                                                             │
                                                                             ▼
                                                                      ┌──────────────┐
                                                                      │ Response +   │
                                                                      │ Actions +    │
                                                                      │ Panel Data   │
                                                                      └──────────────┘
```

### 5.3 Anti-Hallucination Measures

1. **Grounded Responses** — Agents only answer with data retrieved from the database; no fabrication
2. **Confidence Thresholds** — Below 0.7 confidence, the system defaults to `"general"` (safe fallback)
3. **Explicit Negative Examples** — The planner prompt contains disambiguation rules that prevent misrouting
4. **Data Prefetch** — WorkflowPlanner retrieves specific filtered data *before* the agent generates a response
5. **Student Profile Injection** — Real CGPA, registration number, and exemption status are always available (no guessing)
6. **Keyword Overrides** — Hard-coded routing rules for unambiguous queries bypass LLM classification entirely

### 5.4 Database Schema

All models use SQLModel (SQLAlchemy + Pydantic) backed by SQLite.

| Table | Key Fields | Purpose |
|---|---|---|
| `notices` | id, text_hash, source_group, raw_text, parsed_title, category, is_processed | WhatsApp notices (deduplicated by hash) |
| `tasks` | id, title, deadline, status, related_notice_id, is_conflict | Extracted tasks with conflict detection |
| `events` | id, title, start_time, end_time, location, related_notice_id | Calendar events from notices |
| `digests` | id, content, generated_at | Daily AI-generated summaries |
| `attendance` | id, course_code, course_title, percentage, attended, total | Per-course attendance records |
| `course_marks` | id, course_code, course_title, mark_title, max_mark, weightage_pct, score, weightage_mark, status | Individual assessment marks |
| `academic_profile` | id, cgpa, total_credits, overall_attendance, semester_name | Student academic overview |
| `vtop_sessions` | id, cookies_json, csrf_token, established_at, last_validated_at, is_valid | Stored VTOP session cookies |
| `email_notifications` | id, gmail_msg_id, subject, sender, received_at, category, priority, summary, is_read, raw_body | Classified emails + WhatsApp messages |
| `timetable_slots` | id, day, day_of_week, slot, slot_name, course_code, course_name, course_type, venue, start_time, end_time | VIT timetable with slot codes |
| `notifications` | id, title, message, source_agent, priority, is_read, link | Agent-generated user notifications |
| `deadlines` | id, source, title, due_datetime, category, status, source_ref_id, calendar_event_id | Aggregated deadlines from all sources |
| `placement_drives` | id, company_name, drive_date, rounds, status, applied, role, package, eligibility, min_cgpa | Extracted placement drives |
| `prep_checklists` | id, drive_id, items | Preparation checklists per drive |

---

## 6. API Endpoints

### Health & Status

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/status` | Status of all services (ngrok, WhatsApp, VTOP) |

### Chat & AI

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat` | Process message through agentic pipeline |
| POST | `/api/chat/classify` | Lightweight intent classification (no execution) |
| GET | `/api/chat/actions` | Get pending action items |
| POST | `/api/chat/actions/{action_id}/complete` | Mark action as completed |
| GET | `/api/chat/history/{session_id}` | Get conversation history |
| DELETE | `/api/chat/history/{session_id}` | Clear conversation history |

### Academic

| Method | Path | Description |
|---|---|---|
| GET | `/api/academic/attendance` | All attendance records |
| GET | `/api/academic/marks` | All individual mark entries |
| GET | `/api/academic/profile` | Academic profile (CGPA, credits) |
| POST | `/api/academic/sync` | Trigger VTOP data sync |
| POST | `/api/academic/login` | (Deprecated) VTOP login |
| POST | `/api/academic/full-sync` | (Deprecated) Full sync |
| GET | `/api/academic/semesters` | Available VTOP semesters |
| GET | `/api/attendance/risk` | Per-course attendance risk analysis |
| GET | `/api/academic/projection` | CGPA projection for a grade scenario |
| GET | `/api/academic/required-grade` | Grades needed to reach target CGPA |
| GET | `/api/academic/timetable` | Weekly timetable (slot-based) |

### Timetable

| Method | Path | Description |
|---|---|---|
| GET | `/api/timetable` | Timetable grouped by day (resolved times) |
| GET | `/api/timetable/free-slots` | Free time gaps for a given day |

### Gmail & Calendar

| Method | Path | Description |
|---|---|---|
| GET | `/api/gmail/auth-status` | Check Gmail OAuth status |
| POST | `/api/gmail/auth` | Trigger Gmail OAuth flow |
| POST | `/api/gmail/sync` | Fetch + classify emails from Gmail |
| GET | `/api/gmail/notifications` | High-priority email notifications |
| GET | `/api/gmail/all` | All emails with real-time reclassification |
| GET | `/api/gmail/emails-only` | Gmail emails only (excludes WhatsApp) |
| GET | `/api/gmail/whatsapp-only` | WhatsApp messages only |
| POST | `/api/gmail/mark-read/{msg_id}` | Mark email as read |
| POST | `/api/gmail/reclassify` | Re-classify all emails with current rules |
| DELETE | `/api/gmail/clear` | Delete all stored emails |
| POST | `/api/gmail/create-event` | Create Google Calendar event |
| GET | `/api/gmail/calendar-events` | List upcoming calendar events |

### Webhooks (WhatsApp)

| Method | Path | Description |
|---|---|---|
| POST | `/api/webhooks/whatsapp` | Evolution API webhook (NoticeAgent pipeline) |
| POST | `/api/webhooks/whatsapp-n8n` | n8n/UltraMsg webhook (classify + store) |
| GET | `/api/webhooks/whatsapp-groups` | List WhatsApp groups with message counts |

### Notifications

| Method | Path | Description |
|---|---|---|
| GET | `/api/notifications` | List agent-generated notifications |
| POST | `/api/notifications/{id}/read` | Mark notification as read |

### Deadlines

| Method | Path | Description |
|---|---|---|
| POST | `/api/deadlines/sync` | Extract deadlines from all sources |
| GET | `/api/deadlines/timeline` | Upcoming deadlines grouped by week |
| PATCH | `/api/deadlines/{id}` | Update deadline status |

### Placements

| Method | Path | Description |
|---|---|---|
| POST | `/api/placements/sync` | Extract placement drives from Gmail |
| GET | `/api/placements` | All drives with eligibility + checklists |
| POST | `/api/placements/{id}/applied` | Toggle applied status |
| PATCH | `/api/placements/{id}/checklist` | Toggle checklist item completion |

### Profile, Notices, Tasks, Digest

| Method | Path | Description |
|---|---|---|
| GET | `/api/profile` | User profile |
| GET | `/api/notices` | All notices |
| GET | `/api/tasks` | All tasks |
| GET | `/api/digest` | Latest digest |

---

## 7. Setup & Installation

### Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with npm/pnpm
- **Google Cloud Console** project with Gmail API + Calendar API enabled
- **UltraMsg** account (for WhatsApp integration)
- **n8n** instance (self-hosted or cloud) for WhatsApp workflow
- **Groq API key** (free tier available at console.groq.com)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/your-repo/CampusFlow.git
cd CampusFlow/backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
#   GROQ_API_KEY=gsk_...
#   GOOGLE_CLIENT_ID=...
#   GOOGLE_CLIENT_SECRET=...
#   ULTRAMSG_INSTANCE_ID=...
#   ULTRAMSG_TOKEN=...

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd CampusFlow/frontend

# Install dependencies
npm install
# or: pnpm install

# Configure environment
cp .env.example .env.local
# Edit .env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000

# Run development server
npm run dev
```

### First Run Steps

1. **Start backend** → `uvicorn app.main:app --reload`
2. **Start frontend** → `npm run dev`
3. **Authenticate Gmail** → Click "Connect Gmail" in the UI (or POST `/api/gmail/auth`)
4. **Login to VTOP** → Use the embedded login modal, cookies are captured automatically
5. **Select Semester** → Choose from the dropdown, trigger sync
6. **Verify** → Check `/api/academic/attendance` returns data
7. **WhatsApp** → Configure n8n webhook URL to point to your server's `/api/webhooks/whatsapp-n8n`

---

## 8. Innovation & Differentiators

### First-of-Its-Kind Integrations

| Innovation | Description |
|---|---|
| **Unified VTOP + Gmail + WhatsApp** | No existing tool combines all three for VIT students |
| **CDP Cookie Capture** | Industry-grade technique (used by Puppeteer/Playwright) adapted for VTOP auth |
| **Real WhatsApp Monitoring** | 37 groups monitored via UltraMsg + n8n — no WhatsApp Business API required |
| **VIT-Specific Intelligence** | 50+ slot codes mapped, 75% rule with 9.0 exemption, VIT grading scale |
| **Zero Paid AI APIs** | Groq provides free inference for llama-3.3-70b — no OpenAI/Anthropic costs |

### Technical Innovations

1. **CDP Cookie Capture** — Instead of fragile Playwright automation, CampusFlow uses Chrome DevTools Protocol to capture VTOP session cookies from user's real browser login. This is:
   - More reliable (no CAPTCHA issues)
   - Faster (no browser automation overhead after initial login)
   - More secure (user sees the real VTOP login page)

2. **Hybrid Classification** — Emails and WhatsApp messages use the same rule-based classifier with real-time reclassification. No stale categories — every read applies current rules.

3. **Multi-Agent with Workflow Planning** — Instead of simple if/else routing, the WorkflowPlanner uses LLM reasoning to simultaneously decide the agent AND what data to prefetch, reducing hallucination.

4. **Desktop OS Metaphor** — The frontend uses a window manager (`AgentWindow` interface with spawn, minimize, restore, focus, pin operations) giving students a familiar multi-tasking experience.

5. **Anti-Hallucination by Design** — Confidence thresholds, explicit negative examples, data prefetching, and keyword overrides ensure the AI never fabricates academic data.

---

## 9. Future Roadmap

| Phase | Feature | Description |
|---|---|---|
| **v1.1** | Push Notifications | Firebase Cloud Messaging for real-time deadline/attendance alerts |
| **v1.2** | Multi-University Support | Abstract VTOP connector into a plugin system; add SRM, Anna University |
| **v1.3** | Telegram Bot | Lightweight bot interface for students who prefer messaging over web |
| **v2.0** | Mobile App (React Native) | Full mobile experience with offline support and biometric login |
| **v2.1** | Placement Prep Agent | AI-powered mock interview, resume review, DSA practice tracker |
| **v2.2** | Peer Intelligence | Anonymized cohort analytics ("you're in top 20% for attendance") |
| **v3.0** | Course Recommender | FFCS slot optimizer based on workload, professor ratings, and peer reviews |
| **v3.1** | Moodle Integration | Auto-fetch assignments, deadlines, and grades from VIT's Moodle LMS |

---

## 10. Team

| Member | Role | Registration | Contributions |
|---|---|---|---|
| **Ankit Kumar** | Full-stack Developer + AI Pipeline Architect | 23BAI1126 | Backend architecture, multi-agent system, VTOP connector, Gmail integration, database design, API layer, AI orchestration |
| **Pratik** | Frontend Developer + Integrations | Collaborator | Next.js UI, window manager, WhatsApp pipeline, desktop OS design, component library, notification center |

### Technology Ownership

- **Ankit**: FastAPI backend, SQLModel schema, agent orchestration (Orchestrator + WorkflowPlanner), VTOP scraping (sync_orchestrator + scrapers), Gmail classifier, Groq LLM integration, attendance/GPA engines
- **Pratik**: Next.js 15 frontend, AgentShell + WindowManager, TopBar + Desktop + AppGrid components, n8n WhatsApp workflow, UltraMsg integration, UI/UX design

---

## Technical Summary

| Metric | Value |
|---|---|
| Backend Framework | FastAPI (async) |
| Frontend Framework | Next.js 15 + Tailwind CSS |
| Database | SQLite via SQLModel + aiosqlite |
| AI Model | Groq llama-3.3-70b-versatile |
| VTOP Scraping | httpx + BeautifulSoup + CDP cookies |
| Email Integration | Google OAuth2 + Gmail API |
| Calendar Integration | Google Calendar API v3 |
| WhatsApp Pipeline | n8n + UltraMsg → webhook |
| Total API Endpoints | 35+ |
| Database Tables | 14 |
| AI Agents | 12 |
| VIT Slot Codes Mapped | 50+ |
| WhatsApp Groups Monitored | 37 |
| Lines of Backend Code | ~5,000+ |
| Cost of AI APIs | $0 (Groq free tier) |

---

*Built with ❤️ for VIT Chennai students — because campus life shouldn't require 10 browser tabs.*

# CampusFlow — Progress Report

Generated: 2026-06-14

---

## 1. VTOP Login & Sync

**Status:** Complete (Playwright-based login working, HTTP sync working)

### Files:

| File | Purpose | Key Functions |
|------|---------|---------------|
| `backend/vtop_login_browser.py` | Playwright browser login (user solves captcha) | `main()`, CDP cookie extraction |
| `backend/app/routers/vtop_proxy.py` | VTOP API endpoints (launch-login, session-status, semesters, sync) | `launch_login`, `session_status`, `get_semesters`, `trigger_sync` |
| `backend/app/connectors/vtop/sync_orchestrator.py` | HTTP-based scraping with stored cookies | `get_semesters`, `sync_all`, `_scrape_attendance/marks/cgpa` |
| `backend/app/connectors/vtop/session_store.py` | DB-backed VTOP session cookie storage | `save_session`, `get_active_session`, `mark_expired`, `get_cookies_as_httpx` |
| `backend/app/connectors/vtop/session_validator.py` | Validates stored cookies, auto-imports from file | `validate`, `_try_import_from_file` |
| `backend/app/connectors/vtop/scrapers.py` | HTML parsers for VTOP response pages | `parse_attendance`, `parse_marks`, `parse_academic_history` |
| `backend/app/connectors/vtop/browser_scraper.py` | DEPRECATED — Playwright jQuery AJAX scraper | `get_semesters`, `scrape_attendance`, `scrape_marks`, `scrape_cgpa` |
| `backend/app/connectors/vtop/cookie_interceptor.py` | Detects login success from HTTP responses | `detect_login_success`, `extract_cookies`, `validate_cookies` |
| `backend/app/connectors/vtop/proxy_utils.py` | Header stripping, URL rewriting (unused in current flow) | `strip_frame_headers`, `rewrite_urls`, `prepare_upstream_headers` |
| `frontend/src/components/VTOPLoginModal.tsx` | Modal that launches Playwright browser + polls session | Calls `/api/vtop/launch-login`, polls `/session-status` |
| `frontend/src/components/SemesterSelector.tsx` | Semester dropdown popup after login | Fetches `/api/vtop/semesters`, calls `onConfirm(semesterId)` |
| `frontend/src/components/Sidebar.tsx` | Sync button orchestration (check session → login → semester → sync) | `handleSync`, `handleLoginSuccess`, `handleSemesterConfirm` |

### What works:
- Playwright launches, user solves captcha, cookies captured via CDP (bypasses HttpOnly)
- Session cookies stored in DB via SessionStore
- SessionValidator auto-imports from `vtop_session.json` on poll
- HTTP-based sync fetches attendance, marks, CGPA using correct VTOP endpoints
- Correct VTOP endpoints: `StudentTimeTableChn`, `processViewStudentAttendance`, `doStudentMarkView`, `examGradeView/StudentGradeHistory`
- `authorizedID` extracted from content page and included in all requests
- Frontend: Sync button → launch browser modal → semester selector → sync complete
- Single-process lock prevents multiple Playwright instances

### What's missing/broken:
- CGPA extraction returned 0.0 previously (parser was fixed — needs re-verification with fresh sync)
- proxy_utils.py and cookie_interceptor.py are unused in the current Playwright-based flow (leftover from iframe approach)
- No error recovery UI if Playwright crashes silently

---

## 2. Gmail Intelligence Agent

**Status:** Complete

### Files:

| File | Purpose | Key Functions |
|------|---------|---------------|
| `backend/app/connectors/gmail/gmail_client.py` | OAuth2 auth + Gmail API fetching | `authenticate`, `get_messages`, `get_message_detail`, `is_authenticated` |
| `backend/app/connectors/gmail/email_classifier.py` | Rule-based keyword classifier | `classify_email`, `classify_emails` |
| `backend/app/connectors/gmail/email_context.py` | Formats emails as LLM context string | `get_email_context`, `get_email_context_list` |
| `backend/app/routers/gmail.py` | REST API for email operations | `auth_status`, `trigger_auth`, `sync_emails`, `get_notifications`, `get_all_emails`, `reclassify_all` |
| `frontend/src/components/panels/EmailPanel.tsx` | Real Gmail panel with sync, categories, read/unread | Fetches `/api/gmail/all`, syncs, marks read |

### What works:
- OAuth2 flow (opens browser, saves token to `gmail_token.json`)
- Fetches last 50 emails from Gmail API
- Rule-based classification: PLACEMENT > EXAM > FEE > EVENT > ANNOUNCEMENT > GENERAL
- Sender-based override (`"cdc"` in sender → PLACEMENT)
- Stores classified emails in `email_notifications` DB table
- Reclassify endpoint re-runs classifier on all stored emails without re-fetching
- Frontend panel shows real emails with category tabs, priority badges, sync button
- Mark-as-read functionality

### What's missing/broken:
- No pagination for emails (always fetches last 50)
- No incremental sync (checks `gmail_msg_id` uniqueness but no "since last sync" timestamp)
- No email body preview expansion in frontend

---

## 3. Google Calendar Agent

**Status:** Complete

### Files:

| File | Purpose | Key Functions |
|------|---------|---------------|
| `backend/app/connectors/gmail/calendar_client.py` | Google Calendar API client | `create_calendar_event`, `list_upcoming_events` |
| `backend/app/routers/gmail.py` (endpoints) | Calendar REST endpoints | `POST /api/gmail/create-event`, `GET /api/gmail/calendar-events` |
| `backend/app/agents/action_agent.py` | Executes calendar_event actions via LLM | `_create_google_calendar_event` |

### What works:
- OAuth scopes include `calendar.events` (token has both Gmail + Calendar permissions)
- `create_calendar_event()` creates events in primary Google Calendar
- `list_upcoming_events()` fetches next 10-15 events
- Action agent automatically creates Google Calendar events when LLM generates `calendar_event` action type
- Calendar link returned in chat response
- Direct REST endpoint `POST /api/gmail/create-event` for programmatic creation

### What's missing/broken:
- No frontend UI for viewing upcoming calendar events (only accessible via chat or API)
- No event editing/deletion
- End time calculation is simplistic (+1 hour from start)

---

## 4. AI Chat Interface

**Status:** Complete

### Files:

| File | Purpose | Key Functions |
|------|---------|---------------|
| `backend/app/routers/chat.py` | Chat REST endpoint | `POST /api/chat`, `GET /api/chat/history`, `GET /api/chat/actions` |
| `backend/app/agents/orchestrator.py` | Central routing agent (intent → specialist) | `execute`, `_classify_intent`, `_gather_context` |
| `backend/app/agents/academic_agent.py` | Handles marks/attendance/CGPA queries | Uses DB context for academic answers |
| `backend/app/agents/schedule_agent.py` | Creates study plans and schedules | Generates schedule widgets |
| `backend/app/agents/action_agent.py` | Sets reminders, alarms, calendar events | Saves actions to JSON + calls Google Calendar |
| `backend/app/agents/connector_agent.py` | Handles email/WhatsApp/calendar queries | Uses real email context from DB |
| `backend/app/agents/memory.py` | Conversation memory (per session) | `add_message`, `get_history`, `get_summary` |
| `backend/app/utils/llm_client.py` | Groq API client with key rotation | `chat_completion` (uses llama-3.3-70b-versatile) |
| `frontend/src/components/ChatPanel.tsx` | Chat UI with message bubbles + widgets | Sends to `/api/chat`, renders responses + suggested actions |

### What works:
- Intent classification: academic, schedule, action, connector, general
- Multi-turn conversation memory (persisted to disk)
- Academic agent answers from real VTOP data (marks, attendance, CGPA)
- Connector agent reads real emails from DB when classifying as "connector" intent
- Action agent saves actions to JSON files + creates Google Calendar events
- Schedule agent generates study plans with widget data
- Groq API with automatic key rotation on rate limits (supports multiple keys)
- Frontend: chat bubbles, typing indicator, suggested actions, panel navigation
- Chat widgets: calendar events, schedule blocks, task lists

### What's missing/broken:
- Email context injection requires classifier to output `"emails"` in `requires_context` — may not always trigger
- No streaming responses (full response returned after LLM completes)

---

## 5. Email Classifier

**Status:** Complete

### Files:

| File | Purpose | Key Functions |
|------|---------|---------------|
| `backend/app/connectors/gmail/email_classifier.py` | Rule-based keyword matching | `classify_email`, `classify_emails` |

### What works:
- Priority ordering: PLACEMENT checked first (prevents CDC emails from matching EXAM)
- Sender-based override: `"cdc"` or `"placement"` in sender → PLACEMENT
- Keywords cover: exams, results, grades, placements, internships, fees, events, announcements
- Default: GENERAL with low priority
- No external API dependency (works offline, instant)
- Reclassify endpoint re-processes all stored emails

### What's missing/broken:
- No ML-based classification (purely keyword, may miss nuanced emails)
- "drive" keyword may false-positive on Google Drive emails

---

## 6. Frontend Panels

**Status:** Complete

### Files:

| File | Purpose |
|------|---------|
| `frontend/src/components/panels/AttendancePanel.tsx` | Shows attendance data from VTOP |
| `frontend/src/components/panels/MarksPanel.tsx` | Shows marks data from VTOP |
| `frontend/src/components/panels/EmailPanel.tsx` | Real Gmail panel (auth, sync, categories) |
| `frontend/src/components/panels/CalendarPanel.tsx` | Calendar events (fabricated data) |
| `frontend/src/components/panels/WhatsAppPanel.tsx` | WhatsApp messages (fabricated data) |
| `frontend/src/components/panels/TimetablePanel.tsx` | Timetable view (fabricated data) |
| `frontend/src/components/panels/GroupsPanel.tsx` | Study groups (fabricated data) |
| `frontend/src/components/ContextPanel.tsx` | Panel switcher/container |
| `frontend/src/components/Sidebar.tsx` | Navigation + VTOP sync button |

### What works:
- All 7 panels render correctly
- Email panel uses real Gmail data (not fabricated)
- Attendance panel shows real VTOP data
- Marks panel shows real VTOP data
- Panel switching via sidebar navigation
- Dark/light theme toggle

### What's missing/broken:
- Calendar panel uses fabricated data (not connected to Google Calendar API)
- WhatsApp panel uses fabricated data (Evolution API not running — Docker not installed)
- Timetable panel uses fabricated data
- Groups panel uses fabricated data

---

## 7. Database Models

**Status:** Complete

### Files:

| File | Purpose |
|------|---------|
| `backend/app/models.py` | All SQLModel table definitions |
| `backend/app/database.py` | Async SQLite engine + session factory |

### Models defined:
- `Notice` — WhatsApp webhook messages (text_hash, source_group, parsed_title, category)
- `Task` — Extracted tasks with deadlines
- `Event` — Extracted events with start/end times
- `Digest` — Generated briefings
- `Attendance` — VTOP attendance records
- `CourseMark` — VTOP individual mark entries
- `AcademicProfile` — CGPA, total credits, semester
- `VTOPSessionRecord` — Stored VTOP session cookies (cookies_json, csrf_token, is_valid)
- `EmailNotification` — Gmail emails (gmail_msg_id, subject, sender, category, priority, summary, raw_body)

### What works:
- All models auto-create tables via `init_db()` on startup
- Async SQLite via aiosqlite
- Foreign key enforcement enabled

### What's missing/broken:
- No migrations system (schema changes require DB deletion/recreation)
- `campusflow.db` is gitignored (data lost on clone)

---

## 8. Webhook / Integration Points

**Status:** Partial (webhook code exists, but WhatsApp backend not running)

### Files:

| File | Purpose | Key Functions |
|------|---------|---------------|
| `backend/app/routers/webhooks.py` | WhatsApp webhook receiver | `POST /api/webhooks/whatsapp` |
| `backend/app/connectors/whatsapp.py` | Payload normalizer for Evolution API | `extract_text_and_group` |
| `backend/app/agents/notice_agent.py` | LLM extraction from raw messages | Extracts title, category from text |
| `backend/app/agents/scheduler_agent.py` | Inserts notices/tasks/events into DB | Conflict detection |
| `backend/setup_whatsapp.py` | Evolution API instance setup script | `create_instance`, `get_qr_code` |
| `backend/docker-compose.yml` | Evolution API container definition | (if exists) |

### What works:
- Webhook endpoint accepts payloads, deduplicates via hash, triggers agent pipeline
- NoticeAgent → SchedulerAgent pipeline processes messages into tasks/events
- WhatsApp payload normalizer handles Evolution API format
- Setup script configures Evolution API with webhook URL

### What's missing/broken:
- Docker is not installed on this machine
- Evolution API container is not running
- WhatsApp integration is completely non-functional without Docker
- No `docker-compose.yml` found in project root
- WhatsApp panel shows fabricated data only

---

## Summary

| Feature | Status | Real Data | Fabricated |
|---------|--------|-----------|------------|
| VTOP Sync | ✅ Working | Attendance, Marks, CGPA | — |
| Gmail | ✅ Working | Emails classified | — |
| Calendar | ✅ Working | Create events via chat | — |
| AI Chat | ✅ Working | Uses real emails + VTOP data | WhatsApp/calendar context |
| Email Panel | ✅ Working | Real Gmail data | — |
| Attendance Panel | ✅ Working | Real VTOP data | — |
| Marks Panel | ✅ Working | Real VTOP data | — |
| Calendar Panel | ⚠️ Partial | — | Uses fabricated events |
| WhatsApp Panel | ❌ Broken | — | Fabricated (no Docker) |
| Timetable Panel | ⚠️ Partial | — | Fabricated |
| Groups Panel | ⚠️ Partial | — | Fabricated |
| Webhook Pipeline | ❌ Non-functional | — | Requires Docker |

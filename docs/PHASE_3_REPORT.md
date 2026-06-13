# CampusFlow — Phase 3: Intelligence Layer Report

## Executive Summary

Phase 3 transforms CampusFlow from a passive data store into an intelligent processing system. When a WhatsApp message arrives at the webhook, it flows through a three-stage pipeline: **Deduplication → LLM Extraction → Database Insertion with Conflict Detection**. The entire pipeline runs asynchronously in the background, ensuring the webhook responds instantly while the LLM processes the message.

---

## Architecture Overview

```
POST /api/webhooks/whatsapp
│
├── 1. DEDUPLICATION GATE
│   └── SHA-256 hash lookup in DB
│       ├── Hash exists → 200 {"status": "duplicate dropped"}
│       └── Hash new → continue
│
├── 2. IMMEDIATE RESPONSE
│   └── 200 {"status": "processing"}
│
└── 3. BACKGROUND PIPELINE (asyncio.create_task)
    │
    ├── NoticeAgent.execute()
    │   └── Groq LLM (llama-3.3-70b-versatile)
    │       └── Returns structured NoticeExtraction
    │
    └── SchedulerAgent.execute()
        ├── Insert Notice record
        ├── Insert Event (if is_calendar_event)
        └── Insert Task (if is_actionable_task)
            └── ±1 hour conflict detection
```

---

## Component Deep Dive

### 1. Hash Deduplication Utility

**File:** `app/utils/hashing.py`

**Purpose:** WhatsApp groups are notorious for forwarded messages appearing multiple times. This utility ensures the same message is never processed twice, saving LLM API calls and preventing duplicate database entries.

**How it works:**
1. Takes the raw message string
2. Strips leading/trailing whitespace (handles copy-paste variations)
3. Encodes to UTF-8 bytes
4. Generates a SHA-256 hex digest (64-character deterministic hash)

**Why SHA-256:** It's collision-resistant (probability of two different messages producing the same hash is ~1/2^256), fast to compute, and the 64-char hex output fits neatly in a database indexed column.

```python
def compute_text_hash(raw_text: str) -> str:
    cleaned = raw_text.strip()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
```

**Database integration:** The hash is stored in the `Notice.text_hash` column (unique, indexed). Before processing any message, the webhook queries this column — if a match exists, the message is dropped immediately with zero LLM cost.

---

### 2. LLM Extraction Schema

**File:** `app/schemas/extraction.py`

**Purpose:** Enforces a strict contract on the LLM's output. Without this, the LLM could return arbitrary text that crashes downstream code. Pydantic validation guarantees type safety.

**Schema Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `parsed_title` | `str` | Concise title (max 12 words) summarizing the notice |
| `category` | `Literal["Urgent", "Event", "Academic", "General"]` | Classification bucket |
| `is_actionable_task` | `bool` | Does this require student action? |
| `deadline` | `datetime \| None` | When the action is due (ISO 8601) |
| `is_calendar_event` | `bool` | Is this a scheduled event? |
| `start_time` | `datetime \| None` | Event start (ISO 8601) |
| `end_time` | `datetime \| None` | Event end (ISO 8601) |
| `location` | `str \| None` | Physical or virtual venue |

**Validation flow:**
```
LLM output (raw JSON string)
    → NoticeExtraction.model_validate_json(content)
        → Pydantic parses, validates types, enforces Literal constraints
            → Returns typed Python object or raises ValidationError
```

---

### 3. Rolling Key LLM Client

**File:** `app/utils/llm_client.py`

**Purpose:** Provides a single async function `chat_completion()` that abstracts away all Groq API communication, including automatic key rotation when rate limits are hit.

**Key features:**

- **Multi-key support:** Reads `GROQ_API_KEY` from environment (comma-separated), creates one `AsyncGroq` client per key
- **Automatic rotation:** On `RateLimitError` (HTTP 429), immediately rotates to the next key and retries
- **Round-robin:** Keys are tried in circular order — if key 1 fails, try key 2, then key 3, then raise
- **Configurable:** Model, temperature, max tokens, response format, and timeout are all parameterized

**Rate limit handling logic:**
```
Attempt key[0] → 429 → rotate
Attempt key[1] → 429 → rotate
Attempt key[2] → 429 → raise RateLimitError (all exhausted)
```

**Environment configuration:**
```env
GROQ_API_KEY="key1,key2,key3"
GROQ_MODEL=llama-3.3-70b-versatile
```

---

### 4. NoticeAgent

**File:** `app/agents/notice_agent.py`

**Purpose:** The "brain" of the pipeline. Takes raw WhatsApp text and uses Groq's LLM to extract structured entities (tasks, events, deadlines, categories).

**Inherits from:** `BaseAgent` (abstract base class with `async execute(payload: dict) -> dict`)

**Execution flow:**

1. Receives `{"raw_text": "...", "source_group": "..."}`
2. Constructs a system prompt instructing the LLM on the exact JSON schema
3. Calls `chat_completion()` with `response_format={"type": "json_object"}` (forces JSON output)
4. Validates the response through `NoticeExtraction.model_validate_json()`
5. Returns a merged dict: original fields + all extracted fields

**System prompt design:**
- Explicitly lists every field with its type and rules
- Specifies ISO 8601 for all datetime fields
- Instructs "Return ONLY valid JSON matching the schema. No commentary."
- Uses low temperature (0.1) for deterministic, consistent outputs

**Example input/output:**
```
Input:  "URGENT: Submit Cloud Computing assignment by tomorrow 5 PM!"
Output: {
  "parsed_title": "CSE Assignment Submission",
  "category": "Urgent",
  "is_actionable_task": true,
  "deadline": "2026-06-14T17:00:00",
  "is_calendar_event": false,
  "start_time": null,
  "end_time": null,
  "location": null
}
```

---

### 5. SchedulerAgent

**File:** `app/agents/scheduler_agent.py`

**Purpose:** Takes the structured output from NoticeAgent and persists it to the SQLite database, creating Notice, Task, and/or Event records as appropriate. Implements the critical **conflict detection** algorithm.

**Inherits from:** `BaseAgent`

**Execution flow:**

1. Opens an async database session
2. **Insert Notice:** Creates a `Notice` record with the text hash, source group, parsed title, and category. Flushes to get the auto-generated `notice.id`.
3. **Insert Event (conditional):** If `is_calendar_event == True` and `start_time` exists, creates an `Event` record linked to the notice via `related_notice_id` foreign key.
4. **Insert Task with Conflict Detection (conditional):** If `is_actionable_task == True` and `deadline` exists:
   - Runs the conflict detection algorithm
   - Creates a `Task` record with `is_conflict` set accordingly
5. Commits the transaction
6. Returns a summary dict with all created IDs

**Conflict Detection Algorithm:**

This is the most critical piece of business logic in Phase 3. It prevents students from missing overlapping deadlines.

```
Given: new task with category C and deadline D

1. Compute window: [D - 1 hour, D + 1 hour]
2. Query all existing tasks where deadline falls within this window
3. For each task in the window:
   a. Look up its linked Notice via related_notice_id
   b. If that notice has the SAME category as C → CONFLICT
4. Return True if any conflict found, else False
```

**Why ±1 hour?** College deadlines often cluster (e.g., two assignments due "by 5 PM" and "by 6 PM" on the same day are effectively conflicting). The 1-hour window catches these near-misses.

**Why match by category?** A "Cloud Computing assignment due 5 PM" and a "ML club meeting at 5:30 PM" aren't really conflicting (one is Academic, one is Event). But two Academic deadlines within an hour genuinely compete for the student's time.

---

### 6. Webhook Router (Updated)

**File:** `app/routers/webhooks.py`

**Purpose:** The entry point for all incoming WhatsApp messages. Handles the full request lifecycle: receive → deduplicate → dispatch → respond.

**Request flow:**

| Step | Action | Response |
|------|--------|----------|
| Empty text | Skip processing | `{"status": "ignored", "reason": "empty text"}` |
| Hash exists in DB | Drop duplicate | `{"status": "duplicate dropped"}` |
| New message | Fire background pipeline | `{"status": "processing"}` |

**Why background processing?**

The Groq LLM call takes 2-8 seconds. If the webhook waited for it, the WhatsApp provider (Evolution API / Green API) would time out and retry, creating duplicate deliveries. By returning `200 "processing"` immediately and running the pipeline via `asyncio.create_task()`, we:
- Never timeout the webhook provider
- Process at our own pace
- Handle failures gracefully (logged, not user-facing)

**Pipeline error handling:**
```python
async def _run_pipeline(raw_text, source_group):
    try:
        extraction = await _notice_agent.execute(...)
        result = await _scheduler_agent.execute(extraction)
    except Exception:
        logger.exception("Pipeline failed for message: %s...", raw_text[:80])
```

Any failure (LLM timeout, validation error, DB constraint violation) is caught and logged. The user never sees an error — the message simply isn't processed, and can be manually resubmitted later.

---

## Data Flow Diagram

```
WhatsApp Group Message
        │
        ▼
┌─────────────────────────┐
│  POST /api/webhooks/    │
│  whatsapp               │
│                         │
│  1. Print payload       │
│  2. Save sample file    │
│  3. Extract text/group  │
│  4. Compute SHA-256     │
│  5. Check DB for hash   │
│     ├── EXISTS → drop   │
│     └── NEW → continue  │
│  6. create_task(pipeline)│
│  7. Return "processing" │
└─────────────────────────┘
        │ (background)
        ▼
┌─────────────────────────┐
│  NoticeAgent            │
│                         │
│  System prompt +        │
│  raw_text               │
│        │                │
│        ▼                │
│  Groq LLM (rolling keys)│
│        │                │
│        ▼                │
│  Pydantic validation    │
│  (NoticeExtraction)     │
└─────────────────────────┘
        │
        ▼ (structured dict)
┌─────────────────────────┐
│  SchedulerAgent         │
│                         │
│  1. Insert Notice       │
│  2. If event → Insert   │
│     Event               │
│  3. If task:            │
│     a. Check conflicts  │
│     b. Insert Task      │
│  4. Commit transaction  │
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│  SQLite Database        │
│  ├── notices (with hash)│
│  ├── tasks (with flag)  │
│  └── events (with FK)   │
└─────────────────────────┘
```

---

## File Structure (Phase 3 additions)

```
backend/
├── app/
│   ├── agents/
│   │   ├── base.py                 ← (Phase 1) Abstract BaseAgent
│   │   ├── notice_agent.py         ← NEW: LLM entity extraction
│   │   └── scheduler_agent.py      ← NEW: DB insertion + conflict detection
│   ├── routers/
│   │   └── webhooks.py             ← UPDATED: dedup + pipeline dispatch
│   ├── schemas/
│   │   ├── __init__.py             ← NEW: package
│   │   └── extraction.py           ← NEW: NoticeExtraction Pydantic model
│   └── utils/
│       ├── hashing.py              ← NEW: SHA-256 dedup utility
│       ├── llm_client.py           ← NEW: Rolling key Groq client
│       └── user_context.py         ← (Phase 1) Profile reader
├── .env                            ← UPDATED: 3 comma-separated Groq keys
└── requirements.txt                ← UPDATED: added groq, python-dotenv
```

---

## Dependencies Added

| Package | Version | Purpose |
|---------|---------|---------|
| `groq` | latest | Official Groq Python SDK (AsyncGroq for async LLM calls) |
| `python-dotenv` | latest | Load `.env` file into environment variables |

---

## Configuration

```env
# .env file
GROQ_API_KEY="key1,key2,key3"    # Comma-separated for rolling rotation
GROQ_MODEL=llama-3.3-70b-versatile
```

---

## Verified Behavior (Live Test Results)

### Test 1: New message processing
```
POST /api/webhooks/whatsapp
Body: {"text": "URGENT: All 3rd year CSE students must submit their Cloud Computing
       assignments by tomorrow 5 PM! Also the ML club meeting is in Room 402 at 6 PM.",
       "group": "CSE Official 2026"}

Response: {"status": "processing"}

Result in DB:
- Notice: id=1, parsed_title="CSE Assignment Submission", category="Urgent"
- Task: id=1, title="CSE Assignment Submission", deadline=2026-06-14T17:00:00, is_conflict=false
- Event: id=1, title="CSE Assignment Submission", start_time=2026-06-14T18:00:00, location="Room 402"
```

### Test 2: Duplicate detection
```
POST /api/webhooks/whatsapp (same body as above)

Response: {"status": "duplicate dropped"}

Result: No new records created.
```

### Test 3: Empty text handling
```
POST /api/webhooks/whatsapp
Body: {"text": "", "group": "test"}

Response: {"status": "ignored", "reason": "empty text"}
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Background pipeline via `asyncio.create_task()` | Prevents webhook timeout from WhatsApp providers |
| SHA-256 for dedup (not MD5) | Collision-resistant, standard choice for content addressing |
| Pydantic schema validation | Catches malformed LLM output before it hits the database |
| Rolling key rotation | Maximizes free-tier throughput across multiple Groq accounts |
| ±1 hour conflict window | Catches near-miss deadline overlaps without being overly aggressive |
| Category-aware conflict check | Prevents false positives (an event and a task at the same time aren't conflicting) |
| `stream=False` on Groq calls | We need the full response for JSON parsing; streaming adds complexity with no benefit |
| Low temperature (0.1) for extraction | Deterministic, consistent structured output |

---

## Error Handling Matrix

| Failure Point | Behavior | User Impact |
|---------------|----------|-------------|
| Groq API rate limit (single key) | Auto-rotate to next key | None (transparent) |
| All Groq keys rate-limited | Exception caught in pipeline | Message not processed; logged |
| Groq API timeout | Exception caught in pipeline | Message not processed; logged |
| Invalid LLM JSON output | Pydantic ValidationError caught | Message not processed; logged |
| DB constraint violation | Exception caught in pipeline | Message not processed; logged |
| Duplicate message | Dropped at dedup gate | Instant response, no LLM cost |

---

## Unit Test Coverage

All 41 existing tests pass after Phase 3 changes, including updated webhook tests that verify:
- Valid text returns `"processing"` (with mocked pipeline)
- Empty text returns `"ignored"`
- Missing text field returns `"ignored"`
- Pre-existing hash returns `"duplicate dropped"`
- First payload creates `sample_payload.json`
- Subsequent payloads don't overwrite the file

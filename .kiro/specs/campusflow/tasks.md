# Implementation Plan: CampusFlow Phase 1

## Overview

Sequential implementation of the CampusFlow backend skeleton. Tasks are ordered by dependency — database and models first, then utilities, then endpoints, then webhook. Each task is scoped for a single subagent execution.

**Language:** Python 3.11+
**Framework:** FastAPI + SQLModel + aiosqlite
**PBT Library:** Hypothesis

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create `backend/requirements.txt` with: fastapi, uvicorn[standard], sqlmodel, aiosqlite, pydantic, httpx, pytest, pytest-asyncio, hypothesis
  - Create `backend/run.py` entry point that runs uvicorn on `app.main:app` with host `0.0.0.0`, port `8000`, reload enabled
  - Create empty `__init__.py` files for: `app/`, `app/agents/`, `app/routers/`, `app/utils/`
  - _Requirements: 1.3_

- [x] 2. Implement database layer and models
  - [x] 2.1 Create `app/database.py`
    - Async engine with `sqlite+aiosqlite:///./campusflow.db`
    - Add SQLAlchemy event listener (`@event.listens_for(Engine, "connect")`) to execute `PRAGMA foreign_keys=ON` on connect
    - `async_session_maker` using `async_sessionmaker`
    - `get_session()` async generator for dependency injection
    - `init_db()` function that creates all tables using `run_sync(SQLModel.metadata.create_all)`
    - _Requirements: 3.5, 3.7, 3.8_

  - [x] 2.2 Create `app/models.py`
    - Define `Notice` SQLModel table with fields: id (PK), text_hash (unique, indexed), source_group, raw_text, parsed_title, category, is_processed (default False), created_at (default utcnow)
    - Define `Task` SQLModel table with fields: id (PK), title, deadline, status (default "pending"), related_notice_id (FK → notices.id, nullable), is_conflict (default False)
    - Define `Event` SQLModel table with fields: id (PK), title, start_time, end_time, location, related_notice_id (FK → notices.id, nullable)
    - Define `Digest` SQLModel table with fields: id (PK), content, generated_at (default utcnow)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6_

- [x] 3. Implement FastAPI application and health endpoint
  - Create `app/main.py` with:
    - FastAPI app instance
    - `CORSMiddleware` with allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    - Lifespan async context manager that calls `init_db()` on startup
    - `GET /health` route returning `{"status": "healthy"}`
    - Include all routers (to be created) with `/api` prefix
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 4. Implement BaseAgent abstract class
  - Create `app/agents/base.py` with:
    - `BaseAgent` class inheriting from `ABC`
    - Abstract async method `execute(self, payload: dict) -> dict`
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 5. Implement user context utility and profile
  - [x] 5.1 Create `backend/user_profile.json`
    - Include fields: name, branch, college, interests (list), current_focus
    - Populate with sample student data
    - _Requirements: 4.2_

  - [x] 5.2 Create `app/utils/user_context.py`
    - Function `get_user_profile() -> dict` that reads `user_profile.json` from the backend root directory
    - Raises `FileNotFoundError` with descriptive message if file doesn't exist
    - Raises `ValueError` with descriptive message if JSON is invalid
    - Uses `pathlib.Path` for path resolution relative to the backend root
    - _Requirements: 4.1, 4.3_

- [x] 6. Implement read-only API routers
  - [x] 6.1 Create `app/routers/profile.py`
    - `GET /profile` that calls `get_user_profile()` and returns the dict
    - _Requirements: 5.1_

  - [x] 6.2 Create `app/routers/notices.py`
    - `GET /notices` that queries all Notice records from DB and returns as list
    - Route decorator MUST explicitly set `response_model=list[Notice]`
    - Uses `Depends(get_session)` for database session
    - _Requirements: 5.2, 5.6_

  - [x] 6.3 Create `app/routers/tasks.py`
    - `GET /tasks` that queries all Task records from DB and returns as list
    - Route decorator MUST explicitly set `response_model=list[Task]`
    - Uses `Depends(get_session)` for database session
    - _Requirements: 5.3, 5.6_

  - [x] 6.4 Create `app/routers/digest.py`
    - `GET /digest/latest` that returns the digest with max `generated_at`, or `{"message": "No digest available"}` if table is empty
    - Route decorator MUST explicitly set `response_model=Digest | dict` (to handle the "No digest available" fallback)
    - `POST /digest/trigger` that returns `{"status": "not implemented"}`
    - Uses `Depends(get_session)` for database session
    - _Requirements: 5.4, 5.5, 7.1, 7.2_

- [x] 7. Implement WhatsApp webhook router
  - Create `app/routers/webhooks.py`
    - `POST /webhooks/whatsapp` that accepts any JSON body
    - Prints payload to console via `print()`
    - Checks if `sample_payload.json` exists in backend root; if not, saves the payload there
    - Returns `{"status": "received"}` with HTTP 200
    - Uses `pathlib.Path` for file path resolution
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 8. Wire all routers into main application
  - Update `app/main.py` to include all routers:
    - `profile.router` with prefix `/api`
    - `notices.router` with prefix `/api`
    - `tasks.router` with prefix `/api`
    - `digest.router` with prefix `/api`
    - `webhooks.router` with prefix `/api`
  - Verify no import errors and app starts cleanly
  - _Requirements: 1.1, 1.2, 1.3, 5.1, 5.2, 5.3, 5.4, 6.1, 7.1_

- [x] 9. Checkpoint - Verify application starts and health endpoint works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Set up test infrastructure
  - Create `backend/tests/__init__.py`
  - Create `backend/tests/conftest.py` with:
    - Async test client fixture using `httpx.AsyncClient` with `ASGITransport`
    - In-memory SQLite database fixture (`sqlite+aiosqlite:///:memory:`)
    - Override `get_session` dependency for test isolation
    - Cleanup fixtures that reset DB state between tests
  - _Requirements: Testing infrastructure_

- [x] 11. Write unit tests for core components
  - [x] 11.1 Create `backend/tests/test_health.py`
    - Test `GET /health` returns 200 with `{"status": "healthy"}`
    - Test CORS headers are present
    - _Requirements: 1.1, 1.2_

  - [x] 11.2 Create `backend/tests/test_agent.py`
    - Test `BaseAgent` cannot be instantiated directly (TypeError)
    - Test incomplete subclass raises TypeError
    - Test complete subclass can be instantiated and execute called
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 11.3 Create `backend/tests/test_models.py`
    - Test all model fields exist with correct types
    - Test FK constraints on Task and Event
    - Test table creation via init_db
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.8_

  - [x] 11.4 Create `backend/tests/test_profile.py`
    - Test `get_user_profile()` returns valid dict
    - Test missing file raises FileNotFoundError
    - Test invalid JSON raises ValueError
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 11.5 Create `backend/tests/test_endpoints.py`
    - Test `GET /api/profile` returns 200 with profile data
    - Test `GET /api/notices` returns 200 with empty list (no data)
    - Test `GET /api/tasks` returns 200 with empty list (no data)
    - Test `GET /api/digest/latest` returns 200 with "No digest available" message
    - Test `POST /api/digest/trigger` returns 200 with `{"status": "not implemented"}`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.1_

  - [x] 11.6 Create `backend/tests/test_webhooks.py`
    - Test `POST /api/webhooks/whatsapp` returns 200
    - Test first payload creates `sample_payload.json`
    - Test subsequent payloads don't overwrite existing file
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ]* 12. Write property-based tests
  - [ ]* 12.1 Create `backend/tests/test_properties.py` with Hypothesis property tests
    - **Property 1: User profile JSON round-trip** — generate random valid profile dicts, write to temp file, read via utility, verify equality
    - **Validates: Requirements 4.1**

  - [ ]* 12.2 Add property test for API list endpoint round-trip
    - **Property 2: API list endpoint round-trip** — generate random Notice/Task records, insert into test DB, call GET endpoints, verify all records returned with matching data
    - **Validates: Requirements 5.2, 5.3**

  - [ ]* 12.3 Add property test for latest digest selection
    - **Property 3: Latest digest is most recent** — generate random sets of Digest records with distinct timestamps, insert into test DB, call GET /api/digest/latest, verify returned digest has max generated_at
    - **Validates: Requirements 5.4**

  - [ ]* 12.4 Add property test for webhook acceptance
    - **Property 4: Webhook accepts arbitrary JSON** — generate random JSON objects via Hypothesis recursive strategy, POST to webhook, verify 200 response
    - **Validates: Requirements 6.1**

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Task Dependency Graph

```json
{
  "waves": [
    {"tasks": ["1"]},
    {"tasks": ["2"]},
    {"tasks": ["3", "4", "5"]},
    {"tasks": ["6", "7"]},
    {"tasks": ["8"]},
    {"tasks": ["9"]},
    {"tasks": ["10"]},
    {"tasks": ["11", "12"]},
    {"tasks": ["13"]}
  ]
}
```

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Task 8 wires everything together — tasks 3-7 can be developed somewhat independently but task 8 integrates them
- Property tests (task 12) use `hypothesis` with `@settings(max_examples=100)`
- All tests use in-memory SQLite for isolation — no test pollution of the dev database

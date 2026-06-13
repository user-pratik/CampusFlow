# Requirements Document

## Introduction

CampusFlow Phase 1 establishes the core foundation for a unified campus assistant system. This phase delivers the backend skeleton: a FastAPI application with database models, read-only REST endpoints, a webhook stub for WhatsApp message intake, and the abstract agent contract that future intelligence layers will implement. The goal is a lightweight, async Python backend that can be developed and run on a student laptop without heavy dependencies.

## Glossary

- **Backend**: The FastAPI Python application serving the REST API and webhook routes.
- **BaseAgent**: An abstract base class defining the contract for all processing agents in CampusFlow.
- **Notice**: A raw message or announcement extracted from a WhatsApp group, stored with deduplication via text hash.
- **Task**: An actionable item derived from a notice, with a deadline and completion status.
- **Event**: A calendar-worthy occurrence derived from a notice, with time and location details.
- **Digest**: A generated summary of relevant notices, tasks, and events for the user.
- **User_Profile**: A static JSON file containing the student's personal context (name, branch, college, interests, current focus).
- **Webhook**: An HTTP POST endpoint that receives incoming data from an external service (WhatsApp via Evolution API/Green API).
- **Health_Endpoint**: A simple GET route that confirms the server is operational.

## Requirements

### Requirement 1: Initialize Backend Application

**User Story:** As a developer, I want a running FastAPI application with CORS and a health check endpoint, so that I can verify the server is operational and allow cross-origin requests from future frontends.

#### Acceptance Criteria

1. THE Backend SHALL expose a `GET /health` endpoint that returns HTTP 200 with a JSON body indicating the server is running.
2. THE Backend SHALL enable CORS middleware allowing all origins, methods, and headers.
3. WHEN the Backend starts, THE Backend SHALL bind to a configurable host and port and accept HTTP requests.

### Requirement 2: Define Agent Contract

**User Story:** As a developer, I want an abstract base class defining the agent interface, so that all future processing agents share a consistent asynchronous execution contract.

#### Acceptance Criteria

1. THE BaseAgent SHALL define an abstract asynchronous method `execute` that accepts a `payload` parameter of type `dict` and returns a `dict`.
2. THE BaseAgent SHALL be implemented as a Python abstract base class that cannot be instantiated directly.
3. WHEN a subclass of BaseAgent does not implement the `execute` method, THEN the Python runtime SHALL raise a `TypeError` upon instantiation.

### Requirement 3: Build the Database Models

**User Story:** As a developer, I want SQLite database tables for notices, tasks, events, and digests, so that the system can persist and query campus data.

#### Acceptance Criteria

1. THE Backend SHALL define a `Notices` model with fields: `id` (primary key), `text_hash` (string, unique), `source_group` (string), `raw_text` (string), `parsed_title` (string), `category` (string), `is_processed` (boolean), and `created_at` (datetime).
2. THE Backend SHALL define a `Tasks` model with fields: `id` (primary key), `title` (string), `deadline` (datetime), `status` (string, values: "pending" or "completed"), `related_notice_id` (integer), and `is_conflict` (boolean, default: False).
3. THE Backend SHALL define an `Events` model with fields: `id` (primary key), `title` (string), `start_time` (datetime), `end_time` (datetime), `location` (string), and `related_notice_id` (integer).
4. THE Backend SHALL define a `Digests` model with fields: `id` (primary key), `content` (text), and `generated_at` (datetime).
5. THE Backend SHALL use SQLite as the database engine via SQLAlchemy or SQLModel ORM.
6. THE Backend SHALL define `related_notice_id` in the Tasks and Events models as a strict Foreign Key referencing `Notices.id`.
7. THE Backend SHALL configure the SQLite connection using an asynchronous driver (e.g., aiosqlite) to maintain non-blocking operations alongside FastAPI.
8. WHEN the Backend starts, THE Backend SHALL create all defined tables if they do not already exist.

### Requirement 4: Create User Context Utility

**User Story:** As a developer, I want a utility that reads a static user profile from a JSON file, so that future agents can access the student's context without a database lookup.

#### Acceptance Criteria

1. THE Backend SHALL provide a utility function that reads and returns the contents of a `user_profile.json` file as a Python dictionary.
2. THE Backend SHALL include a `user_profile.json` file containing these fields: `name` (string), `branch` (string), `college` (string), `interests` (list of strings), and `current_focus` (string).
3. IF the `user_profile.json` file does not exist or is unreadable, THEN the utility SHALL raise a descriptive error.

### Requirement 5: Create Read-Only REST Endpoints

**User Story:** As a developer, I want read-only API endpoints for profile, notices, tasks, and the latest digest, so that future frontends and agents can retrieve stored data.

#### Acceptance Criteria

1. THE Backend SHALL expose a `GET /api/profile` endpoint that returns the user profile data as JSON with HTTP 200.
2. THE Backend SHALL expose a `GET /api/notices` endpoint that returns all notices from the database as a JSON list with HTTP 200.
3. THE Backend SHALL expose a `GET /api/tasks` endpoint that returns all tasks from the database as a JSON list with HTTP 200.
4. THE Backend SHALL expose a `GET /api/digest/latest` endpoint that returns the most recently generated digest as JSON with HTTP 200.
5. IF the digest table contains no records, THEN the `GET /api/digest/latest` endpoint SHALL return a JSON response indicating no digest is available with HTTP 200.
6. THE Backend SHALL use Pydantic response models (or SQLModel equivalent) to serialize the database records into JSON format for all GET endpoints.

### Requirement 6: Stub the WhatsApp Webhook Route

**User Story:** As a developer, I want a webhook endpoint that accepts WhatsApp payloads, so that I can capture real message data for future processing development.

#### Acceptance Criteria

1. THE Backend SHALL expose a `POST /api/webhooks/whatsapp` endpoint that accepts any JSON payload and returns HTTP 200.
2. WHEN the webhook receives a payload, THE Backend SHALL print the payload content to the server console.
3. WHEN the webhook receives a payload and a file named `sample_payload.json` does not exist, THEN THE Backend SHALL save the raw payload to `sample_payload.json`.
4. WHEN the webhook receives a payload and a file named `sample_payload.json` already exists, THEN THE Backend SHALL not overwrite the existing file.

### Requirement 7: Reserve Demo Digest Trigger Route

**User Story:** As a developer, I want a reserved route for triggering digest generation, so that the endpoint is available for Phase 5 integration without breaking API contracts.

#### Acceptance Criteria

1. THE Backend SHALL expose a `POST /api/digest/trigger` endpoint that returns `{"status": "not implemented"}` as JSON with HTTP 200.
2. THE Backend SHALL not implement any digest generation logic in this endpoint.

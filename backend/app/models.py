"""SQLModel table definitions for CampusFlow.

Defines Notice, Task, Event, and Digest models backed by SQLite.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class Notice(SQLModel, table=True):
    __tablename__ = "notices"

    id: int | None = Field(default=None, primary_key=True)
    text_hash: str = Field(unique=True, index=True)
    source_group: str
    raw_text: str
    parsed_title: str
    category: str
    is_processed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    deadline: datetime
    status: str = Field(default="pending")
    related_notice_id: int | None = Field(default=None, foreign_key="notices.id")
    is_conflict: bool = Field(default=False)


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    start_time: datetime
    end_time: datetime
    location: str
    related_notice_id: int | None = Field(default=None, foreign_key="notices.id")


class Digest(SQLModel, table=True):
    __tablename__ = "digests"

    id: int | None = Field(default=None, primary_key=True)
    content: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Phase 6: Academic Data Models ────────────────────────────────────────────


class Attendance(SQLModel, table=True):
    __tablename__ = "attendance"

    id: int | None = Field(default=None, primary_key=True)
    course_code: str = Field(index=True)
    course_title: str
    percentage: float
    attended: int
    total: int
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CourseMark(SQLModel, table=True):
    """Individual mark entry — one row per assessment per course."""
    __tablename__ = "course_marks"

    id: int | None = Field(default=None, primary_key=True)
    course_code: str = Field(index=True)
    course_title: str
    mark_title: str  # e.g. "CAT 1", "Assessment - 1", "Final Assessment Test"
    max_mark: float | None = None
    weightage_pct: float | None = None  # Weightage %
    score: float | None = None  # Scored Mark
    weightage_mark: float | None = None  # Weightage Mark (computed by VTOP)
    status: str | None = None  # "Present" / "Absent"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AcademicProfile(SQLModel, table=True):
    __tablename__ = "academic_profile"

    id: int | None = Field(default=None, primary_key=True)
    cgpa: float
    total_credits: int
    overall_attendance: float | None = None  # percentage
    semester_name: str | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Phase 7: Embedded VTOP Login ─────────────────────────────────────────────


class VTOPSessionRecord(SQLModel, table=True):
    __tablename__ = "vtop_sessions"

    id: int | None = Field(default=None, primary_key=True)
    cookies_json: str  # JSON-serialized cookie list [{name, value, domain, path}]
    csrf_token: str | None = Field(default=None)
    established_at: datetime = Field(default_factory=datetime.utcnow)
    last_validated_at: datetime | None = Field(default=None)
    is_valid: bool = Field(default=True)


# ─── Gmail Integration ────────────────────────────────────────────────────────


class EmailNotification(SQLModel, table=True):
    """Classified email notification from Gmail."""

    __tablename__ = "email_notifications"

    id: int | None = Field(default=None, primary_key=True)
    gmail_msg_id: str = Field(unique=True, index=True)
    subject: str | None = None
    sender: str | None = None
    received_at: datetime | None = None
    category: str | None = None
    priority: str | None = None
    summary: str | None = None
    is_read: bool = Field(default=False)
    raw_body: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Timetable ────────────────────────────────────────────────────────────────


class TimetableSlot(SQLModel, table=True):
    """A single timetable slot scraped from VTOP."""

    __tablename__ = "timetable_slots"

    id: int | None = Field(default=None, primary_key=True)
    day: str = ""  # Day of week (may be empty for VIT slot-based system)
    slot: str = ""  # VIT slot code e.g. "A1+TA1", "L31+L32"
    course_code: str = ""
    course_type: str = "TH"  # TH, ETH, LAB
    venue: str | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Notifications ────────────────────────────────────────────────────────────


class Notification(SQLModel, table=True):
    """Agent-generated notification surfaced to the user."""

    __tablename__ = "notifications"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    message: str
    source_agent: str  # e.g. "Attendance Agent", "Deadline Agent"
    priority: str = Field(default="normal")  # "low", "normal", "high", "urgent"
    is_read: bool = Field(default=False, index=True)
    link: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Deadlines ────────────────────────────────────────────────────────────────


class Deadline(SQLModel, table=True):
    """Aggregated deadline from various sources."""

    __tablename__ = "deadlines"

    id: int | None = Field(default=None, primary_key=True)
    source: str  # "gmail" or "manual"
    title: str
    due_datetime: datetime
    category: str  # "fee", "placement", "exam", "academic", "event"
    status: str = Field(default="upcoming")  # "upcoming", "completed", "missed"
    source_ref_id: str | None = Field(default=None, index=True)
    calendar_event_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Placements ───────────────────────────────────────────────────────────────


class PlacementDrive(SQLModel, table=True):
    """Placement drive extracted from Gmail emails."""

    __tablename__ = "placement_drives"

    id: int | None = Field(default=None, primary_key=True)
    company_name: str
    drive_date: datetime | None = None
    rounds: str = Field(default="[]")
    status: str = Field(default="upcoming")
    applied: bool = Field(default=False)
    source_email_id: str | None = Field(default=None, unique=True, index=True)
    role: str | None = None
    package: str | None = None
    eligibility: str | None = None
    eligible_degree: str | None = None
    eligible_batch: str | None = None
    min_cgpa: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PrepChecklist(SQLModel, table=True):
    """Preparation checklist linked to a PlacementDrive."""

    __tablename__ = "prep_checklists"

    id: int | None = Field(default=None, primary_key=True)
    drive_id: int = Field(foreign_key="placement_drives.id", index=True)
    items: str = Field(default="[]")
    created_at: datetime = Field(default_factory=datetime.utcnow)

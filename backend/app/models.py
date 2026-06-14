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

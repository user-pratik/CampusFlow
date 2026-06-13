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

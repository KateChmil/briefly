import enum
import uuid
from datetime import date as date_t
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SpaceStatus(str, enum.Enum):
    interviewing = "interviewing"
    generating = "generating"
    ready = "ready"


class SourceOrigin(str, enum.Enum):
    upload = "upload"
    teams = "teams"
    canvas = "canvas"


class ArtifactKind(str, enum.Enum):
    study_plan = "study_plan"
    notes = "notes"
    sample_test = "sample_test"
    flashcards = "flashcards"


class SubjectSpace(Base):
    __tablename__ = "subject_spaces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[SpaceStatus] = mapped_column(
        Enum(SpaceStatus), default=SpaceStatus.interviewing
    )
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    sources: Mapped[list["Source"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="space",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["StudySession"]] = relationship(
        back_populates="space",
        cascade="all, delete-orphan",
        order_by="StudySession.date",
    )
    events: Mapped[list["CalendarEvent"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )
    user_notes: Mapped[list["UserNote"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )


def space_exam_date(space: SubjectSpace) -> date_t | None:
    """The exam date from the student profile, if it is a valid ISO date."""
    raw = (space.profile or {}).get("exam_date")
    if not isinstance(raw, str):
        return None
    try:
        return date_t.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    space_id: Mapped[str] = mapped_column(
        ForeignKey("subject_spaces.id", ondelete="CASCADE")
    )
    origin: Mapped[SourceOrigin] = mapped_column(Enum(SourceOrigin))
    filename: Mapped[str] = mapped_column(String(300))
    mime_type: Mapped[str] = mapped_column(String(100), default="")
    storage_path: Mapped[str] = mapped_column(String(600))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    teams_ref: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    space: Mapped[SubjectSpace] = relationship(back_populates="sources")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    space_id: Mapped[str] = mapped_column(
        ForeignKey("subject_spaces.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    space: Mapped[SubjectSpace] = relationship(back_populates="messages")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    space_id: Mapped[str] = mapped_column(
        ForeignKey("subject_spaces.id", ondelete="CASCADE")
    )
    kind: Mapped[ArtifactKind] = mapped_column(Enum(ArtifactKind))
    format: Mapped[str] = mapped_column(String(10), default="markdown")
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    space: Mapped[SubjectSpace] = relationship(back_populates="artifacts")


class StudySession(Base):
    """One dated block from the generated study plan (checkable, shown on the calendar)."""

    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    space_id: Mapped[str] = mapped_column(
        ForeignKey("subject_spaces.id", ondelete="CASCADE")
    )
    date: Mapped[date_t] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(300), default="")
    minutes: Mapped[int] = mapped_column(Integer, default=45)
    kind: Mapped[str] = mapped_column(String(20), default="study")
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    space: Mapped[SubjectSpace] = relationship(back_populates="sessions")


class CalendarEvent(Base):
    """Classes, exams and other events: added by hand or imported from an ICS feed."""

    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    space_id: Mapped[str | None] = mapped_column(
        ForeignKey("subject_spaces.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300))
    date: Mapped[date_t] = mapped_column(Date)
    start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="other")
    source: Mapped[str] = mapped_column(String(20), default="manual")
    external_uid: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    space: Mapped[SubjectSpace | None] = relationship(back_populates="events")


class UserNote(Base):
    """A note the student wrote themselves ("My notes"), per subject space."""

    __tablename__ = "user_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    space_id: Mapped[str] = mapped_column(
        ForeignKey("subject_spaces.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    space: Mapped[SubjectSpace] = relationship(back_populates="user_notes")

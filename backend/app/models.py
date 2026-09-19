import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
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


class ArtifactKind(str, enum.Enum):
    study_plan = "study_plan"
    notes = "notes"
    sample_test = "sample_test"


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

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class SpaceCreate(BaseModel):
    name: str


class SpaceSummary(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    source_count: int = 0
    artifact_count: int = 0
    exam_date: date | None = None
    sessions_total: int = 0
    sessions_done: int = 0


class SourceOut(BaseModel):
    id: str
    origin: str
    filename: str
    mime_type: str
    teams_ref: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SpaceDetail(BaseModel):
    id: str
    name: str
    status: str
    profile: dict | None
    exam_date: date | None = None
    created_at: datetime
    sources: list[SourceOut] = []


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class ChatResponse(BaseModel):
    message: ChatMessageOut
    space_status: str
    # True when the interview finished and materials are being generated.
    profile_completed: bool = False
    # True when the tutor changed the profile and the plan is being rebuilt.
    plan_updating: bool = False


class ArtifactOut(BaseModel):
    id: int
    kind: str
    format: str
    content: str
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamsItemOut(BaseModel):
    id: str
    name: str


class TeamsImportRequest(BaseModel):
    file_ids: list[str]


class SessionOut(BaseModel):
    id: int
    space_id: str
    date: date
    title: str
    topic: str
    minutes: int
    kind: str
    done: bool

    model_config = {"from_attributes": True}


class SessionPatch(BaseModel):
    done: bool


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    date: date
    start_time: str | None = Field(default=None, pattern=HHMM)
    end_time: str | None = Field(default=None, pattern=HHMM)
    kind: Literal["class", "exam", "other"] = "other"
    space_id: str | None = None
    description: str = Field(default="", max_length=1000)


class CalendarItem(BaseModel):
    """One row on the calendar: an event, a study session or a profile exam date."""

    id: str
    type: Literal["event", "session", "exam"]
    date: date
    start_time: str | None = None
    end_time: str | None = None
    title: str
    kind: str
    space_id: str | None = None
    space_name: str | None = None
    done: bool | None = None
    minutes: int | None = None
    topic: str | None = None
    deletable: bool = False


class ImportUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    space_id: str | None = None


class ImportResult(BaseModel):
    imported: int
    skipped: int

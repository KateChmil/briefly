from datetime import datetime

from pydantic import BaseModel


class SpaceCreate(BaseModel):
    name: str


class SpaceSummary(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    source_count: int = 0
    artifact_count: int = 0


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
    created_at: datetime
    sources: list[SourceOut] = []


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    content: str


class ChatResponse(BaseModel):
    message: ChatMessageOut
    space_status: str
    profile_completed: bool = False


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

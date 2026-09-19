import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import ChatMessage, SubjectSpace, space_exam_date
from ..schemas import (
    SessionOut,
    SourceOut,
    SpaceCreate,
    SpaceDetail,
    SpaceSummary,
)

router = APIRouter(prefix="/api/spaces", tags=["spaces"])

GREETING = (
    "Hi! I'm Briefly, your study assistant for **{name}**.\n\n"
    "To build your study plan, notes and a practice test, I need a few "
    "details: what are you working toward (an exam, a deadline, general "
    "mastery), and when?\n\n"
    "You can also attach files or import them from Teams in the Sources "
    "panel on the left."
)


def get_space(db: Session, space_id: str) -> SubjectSpace:
    space = db.get(SubjectSpace, space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return space


def to_detail(space: SubjectSpace) -> SpaceDetail:
    return SpaceDetail(
        id=space.id,
        name=space.name,
        status=space.status.value,
        profile=space.profile,
        exam_date=space_exam_date(space),
        created_at=space.created_at,
        sources=[SourceOut.model_validate(s) for s in space.sources],
    )


@router.post("", response_model=SpaceDetail, status_code=201)
def create_space(req: SpaceCreate, db: Session = Depends(get_db)):
    name = req.name.strip()[:200]
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    space = SubjectSpace(name=name)
    db.add(space)
    db.flush()
    db.add(
        ChatMessage(
            space_id=space.id,
            role="assistant",
            content=GREETING.format(name=name),
        )
    )
    db.commit()
    db.refresh(space)
    return to_detail(space)


@router.get("", response_model=list[SpaceSummary])
def list_spaces(db: Session = Depends(get_db)):
    spaces = db.scalars(
        select(SubjectSpace).order_by(SubjectSpace.created_at.desc())
    ).all()
    return [
        SpaceSummary(
            id=s.id,
            name=s.name,
            status=s.status.value,
            created_at=s.created_at,
            source_count=len(s.sources),
            artifact_count=len(s.artifacts),
            exam_date=space_exam_date(s),
            sessions_total=len(s.sessions),
            sessions_done=sum(1 for x in s.sessions if x.done),
        )
        for s in spaces
    ]


@router.get("/{space_id}", response_model=SpaceDetail)
def get_space_detail(space_id: str, db: Session = Depends(get_db)):
    return to_detail(get_space(db, space_id))


@router.get("/{space_id}/sessions", response_model=list[SessionOut])
def list_sessions(space_id: str, db: Session = Depends(get_db)):
    return get_space(db, space_id).sessions


@router.delete("/{space_id}", status_code=204)
def delete_space(space_id: str, db: Session = Depends(get_db)):
    space = get_space(db, space_id)
    shutil.rmtree(Path(settings.storage_dir) / space_id, ignore_errors=True)
    db.delete(space)
    db.commit()

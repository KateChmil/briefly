from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import UserNote, utcnow
from ..schemas import (
    NoteEnhanceRequest,
    NoteEnhanceResult,
    UserNoteCreate,
    UserNoteOut,
    UserNotePatch,
)
from ..services import generation, notes_ai
from .spaces import get_space

router = APIRouter(tags=["notes"])


def get_note(db: Session, note_id: int) -> UserNote:
    note = db.get(UserNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.get("/api/spaces/{space_id}/notes", response_model=list[UserNoteOut])
def list_notes(space_id: str, db: Session = Depends(get_db)):
    get_space(db, space_id)
    return db.scalars(
        select(UserNote)
        .where(UserNote.space_id == space_id)
        .order_by(UserNote.updated_at.desc())
    ).all()


@router.post(
    "/api/spaces/{space_id}/notes", response_model=UserNoteOut, status_code=201
)
def create_note(
    space_id: str, req: UserNoteCreate, db: Session = Depends(get_db)
):
    get_space(db, space_id)
    note = UserNote(
        space_id=space_id,
        title=req.title.strip()[:200] or "Untitled note",
        content=req.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/api/notes/{note_id}", response_model=UserNoteOut)
def update_note(
    note_id: int, req: UserNotePatch, db: Session = Depends(get_db)
):
    note = get_note(db, note_id)
    if req.title is not None:
        note.title = req.title.strip()[:200]
    if req.content is not None:
        note.content = req.content
    note.updated_at = utcnow()
    db.commit()
    db.refresh(note)
    return note


@router.delete("/api/notes/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    db.delete(get_note(db, note_id))
    db.commit()


@router.post("/api/notes/{note_id}/enhance", response_model=NoteEnhanceResult)
def enhance(
    note_id: int, req: NoteEnhanceRequest, db: Session = Depends(get_db)
):
    """One AI action on the note; returns Markdown (and cards) without saving."""
    note = get_note(db, note_id)
    if not note.content.strip():
        raise HTTPException(
            status_code=400,
            detail="This note is empty — write something first.",
        )
    space = get_space(db, note.space_id)
    try:
        return notes_ai.enhance_note(space, note, req.action)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=(
                "The AI could not help right now: "
                f"{generation.describe_error(e)}"
            ),
        )

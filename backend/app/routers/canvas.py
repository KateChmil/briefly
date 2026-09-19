from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import CalendarEvent, Source, SourceOrigin, new_id
from ..schemas import (
    CanvasAssignmentOut,
    CanvasAssignmentsImportRequest,
    CanvasImportRequest,
    CanvasItemOut,
    CanvasStatusOut,
    ImportResult,
    SourceOut,
)
from ..services import ics
from ..services.canvas_provider import (
    ALL_DAY_DUE,
    CanvasError,
    CanvasProvider,
    HttpCanvasProvider,
    MockCanvasProvider,
)
from ..services.extract import extract_text
from .spaces import get_space

router = APIRouter(prefix="/api", tags=["canvas"])


def get_provider() -> CanvasProvider:
    """Real Canvas when CANVAS_BASE_URL (https) + CANVAS_TOKEN are set, else mock."""
    if settings.canvas_base_url and settings.canvas_token:
        try:
            return HttpCanvasProvider(
                settings.canvas_base_url, settings.canvas_token
            )
        except ValueError:
            pass  # misconfigured (non-https base URL) -> stay on the mock
    return MockCanvasProvider(settings.mock_canvas_dir)


def _provider_error(e: Exception) -> HTTPException:
    status = 502 if isinstance(e, CanvasError) else 400
    return HTTPException(status_code=status, detail=str(e))


@router.get("/canvas/status", response_model=CanvasStatusOut)
def canvas_status():
    mode = "live" if isinstance(get_provider(), HttpCanvasProvider) else "mock"
    return {"mode": mode}


@router.get("/canvas/courses", response_model=list[CanvasItemOut])
def list_courses():
    try:
        return get_provider().list_courses()
    except (CanvasError, ValueError) as e:
        raise _provider_error(e)


@router.get(
    "/canvas/courses/{course_id}/assignments",
    response_model=list[CanvasAssignmentOut],
)
def list_assignments(course_id: str):
    try:
        return get_provider().list_assignments(course_id)
    except (CanvasError, ValueError) as e:
        raise _provider_error(e)


@router.get("/canvas/courses/{course_id}/files", response_model=list[CanvasItemOut])
def list_files(course_id: str):
    try:
        return get_provider().list_files(course_id)
    except (CanvasError, ValueError) as e:
        raise _provider_error(e)


class CanvasImportResult(BaseModel):
    imported: list[SourceOut]
    skipped: list[dict]


@router.post("/spaces/{space_id}/sources/canvas", response_model=CanvasImportResult)
def import_from_canvas(
    space_id: str,
    req: CanvasImportRequest,
    db: Session = Depends(get_db),
):
    get_space(db, space_id)
    provider = get_provider()
    dest_dir = Path(settings.storage_dir) / space_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    imported, skipped = [], []
    for file_id in req.file_ids:
        try:
            filename, data = provider.read_file(file_id)
            text = extract_text(filename, data)
        except (ValueError, FileNotFoundError) as e:
            skipped.append({"file_id": file_id, "reason": str(e)})
            continue
        except Exception:
            skipped.append({"file_id": file_id, "reason": "Could not read file"})
            continue
        if not text.strip():
            skipped.append({"file_id": file_id, "reason": "No readable text"})
            continue

        dest = dest_dir / f"{new_id()}_{filename}"
        dest.write_bytes(data)
        src = Source(
            space_id=space_id,
            origin=SourceOrigin.canvas,
            filename=filename,
            mime_type="",
            storage_path=str(dest),
            extracted_text=text,
            teams_ref={"file_id": file_id},
        )
        db.add(src)
        imported.append(src)
    db.commit()
    for s in imported:
        db.refresh(s)
    return CanvasImportResult(imported=imported, skipped=skipped)


@router.post(
    "/spaces/{space_id}/calendar/canvas-assignments", response_model=ImportResult
)
def import_canvas_assignments(
    space_id: str,
    req: CanvasAssignmentsImportRequest,
    db: Session = Depends(get_db),
):
    """Create calendar events from a course's assignment due dates.

    Idempotent: the Canvas assignment id is stored in external_uid and repeat
    imports skip it. Titles containing exam words become kind="exam".
    """
    get_space(db, space_id)
    try:
        assignments = get_provider().list_assignments(req.course_id)
    except (CanvasError, ValueError) as e:
        raise _provider_error(e)

    existing = {
        e.external_uid
        for e in db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.space_id == space_id,
                CalendarEvent.source == "canvas",
            )
        )
    }
    imported = skipped = 0
    for a in assignments:
        if a.due_at is None:
            skipped += 1
            continue
        uid = f"canvas:{req.course_id}:{a.id}"
        if uid in existing:
            skipped += 1
            continue
        existing.add(uid)
        db.add(
            CalendarEvent(
                space_id=space_id,
                title=a.name[:300],
                date=a.due_at.date(),
                start_time=(
                    None
                    if a.due_at.time() == ALL_DAY_DUE
                    else a.due_at.strftime("%H:%M")
                ),
                kind="exam" if ics.EXAM_WORDS.search(a.name) else "other",
                source="canvas",
                external_uid=uid,
                description=(a.description or "")[:1000],
            )
        )
        imported += 1
    db.commit()
    return ImportResult(imported=imported, skipped=skipped)

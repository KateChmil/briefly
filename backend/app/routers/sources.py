import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Source, SourceOrigin, new_id
from ..schemas import SourceOut
from ..services.extract import extract_text
from .spaces import get_space

router = APIRouter(prefix="/api/spaces/{space_id}/sources", tags=["sources"])


def safe_filename(name: str | None) -> str:
    """Strip any directory part and unusual characters from a client-supplied name."""
    base = (name or "").replace("\\", "/").split("/")[-1]
    base = re.sub(r"[^\w.\- ]", "_", base, flags=re.UNICODE).strip(" .")
    return base[:120] or "file"


@router.get("", response_model=list[SourceOut])
def list_sources(space_id: str, db: Session = Depends(get_db)):
    get_space(db, space_id)
    return db.scalars(
        select(Source)
        .where(Source.space_id == space_id)
        .order_by(Source.created_at)
    ).all()


@router.post("", response_model=SourceOut, status_code=201)
def upload_source(
    space_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    get_space(db, space_id)
    filename = safe_filename(file.filename)
    limit = settings.max_upload_bytes
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large (max {limit // (1024 * 1024)} MB).",
        )
    try:
        text = extract_text(filename, data)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=422, detail="Could not read that file. Is it corrupted?"
        )
    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No readable text found (scanned PDFs need OCR first).",
        )

    dest_dir = Path(settings.storage_dir) / space_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{new_id()}_{filename}"
    dest.write_bytes(data)

    src = Source(
        space_id=space_id,
        origin=SourceOrigin.upload,
        filename=filename,
        mime_type=(file.content_type or "")[:100],
        storage_path=str(dest),
        extracted_text=text,
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


@router.delete("/{source_id}", status_code=204)
def delete_source(space_id: str, source_id: str, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if src is None or src.space_id != space_id:
        raise HTTPException(status_code=404, detail="Source not found")
    Path(src.storage_path).unlink(missing_ok=True)
    db.delete(src)
    db.commit()

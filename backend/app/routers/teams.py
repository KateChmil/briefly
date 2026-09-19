from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Source, SourceOrigin, new_id
from ..schemas import SourceOut, TeamsImportRequest, TeamsItemOut
from ..services.extract import extract_text
from ..services.teams_provider import MockTeamsProvider
from .spaces import get_space

router = APIRouter(prefix="/api", tags=["teams"])


def get_provider() -> MockTeamsProvider:
    return MockTeamsProvider(settings.mock_teams_dir)


@router.get("/teams", response_model=list[TeamsItemOut])
def list_teams():
    return get_provider().list_teams()


@router.get("/teams/channels", response_model=list[TeamsItemOut])
def list_channels(team_id: str):
    try:
        return get_provider().list_channels(team_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/teams/files", response_model=list[TeamsItemOut])
def list_files(channel_id: str):
    try:
        return get_provider().list_files(channel_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ImportResult(BaseModel):
    imported: list[SourceOut]
    skipped: list[dict]


@router.post("/spaces/{space_id}/sources/teams", response_model=ImportResult)
def import_from_teams(
    space_id: str,
    req: TeamsImportRequest,
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

        dest = dest_dir / f"{new_id()}_{filename}"
        dest.write_bytes(data)
        src = Source(
            space_id=space_id,
            origin=SourceOrigin.teams,
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
    return ImportResult(imported=imported, skipped=skipped)

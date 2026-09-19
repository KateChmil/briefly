from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Artifact, ArtifactKind
from ..schemas import ArtifactOut
from ..services import generation
from .spaces import get_space

router = APIRouter(prefix="/api/spaces/{space_id}/artifacts", tags=["artifacts"])


def _latest(db: Session, space_id: str, kind: ArtifactKind) -> Artifact | None:
    return db.scalars(
        select(Artifact)
        .where(Artifact.space_id == space_id, Artifact.kind == kind)
        .order_by(Artifact.version.desc())
        .limit(1)
    ).first()


@router.get("", response_model=list[ArtifactOut])
def list_artifacts(space_id: str, db: Session = Depends(get_db)):
    get_space(db, space_id)
    rows = db.scalars(
        select(Artifact)
        .where(Artifact.space_id == space_id)
        .order_by(Artifact.kind, Artifact.version.desc())
    ).all()
    latest: dict[ArtifactKind, Artifact] = {}
    for a in rows:
        latest.setdefault(a.kind, a)
    return list(latest.values())


@router.get("/{kind}", response_model=ArtifactOut)
def get_artifact(space_id: str, kind: ArtifactKind, db: Session = Depends(get_db)):
    get_space(db, space_id)
    artifact = _latest(db, space_id, kind)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.post("/{kind}/regenerate", response_model=ArtifactOut)
def regenerate_artifact(
    space_id: str, kind: ArtifactKind, db: Session = Depends(get_db)
):
    space = get_space(db, space_id)
    try:
        content, fmt = generation.generate_one(space, kind)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI request failed: {e}")
    prev = _latest(db, space_id, kind)
    artifact = Artifact(
        space_id=space_id,
        kind=kind,
        format=fmt,
        content=content,
        version=(prev.version + 1) if prev else 1,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact

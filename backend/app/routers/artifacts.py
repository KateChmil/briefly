from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Artifact, ArtifactKind, SpaceStatus
from ..schemas import ArtifactOut, SpaceDetail
from ..services import generation
from .spaces import get_space, to_detail

router = APIRouter(prefix="/api/spaces/{space_id}", tags=["artifacts"])


def _latest(db: Session, space_id: str, kind: ArtifactKind) -> Artifact | None:
    return db.scalars(
        select(Artifact)
        .where(Artifact.space_id == space_id, Artifact.kind == kind)
        .order_by(Artifact.version.desc())
        .limit(1)
    ).first()


@router.get("/artifacts", response_model=list[ArtifactOut])
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


@router.get("/artifacts/{kind}", response_model=ArtifactOut)
def get_artifact(space_id: str, kind: ArtifactKind, db: Session = Depends(get_db)):
    get_space(db, space_id)
    artifact = _latest(db, space_id, kind)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.post("/artifacts/{kind}/regenerate", response_model=ArtifactOut)
def regenerate_artifact(
    space_id: str, kind: ArtifactKind, db: Session = Depends(get_db)
):
    space = get_space(db, space_id)
    if space.status == SpaceStatus.generating:
        raise HTTPException(status_code=409, detail="Already generating.")
    try:
        return generation.regenerate_one(db, space, kind)
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Could not regenerate: {generation.describe_error(e)}"
        )


@router.post("/generate", response_model=SpaceDetail, status_code=202)
def generate_all(
    space_id: str, background: BackgroundTasks, db: Session = Depends(get_db)
):
    """(Re)build every artifact from the saved profile, e.g. after a failed run."""
    space = get_space(db, space_id)
    if not space.profile:
        raise HTTPException(
            status_code=400, detail="Finish the chat interview first."
        )
    if space.status == SpaceStatus.generating:
        raise HTTPException(status_code=409, detail="Already generating.")
    space.status = SpaceStatus.generating
    db.commit()
    background.add_task(generation.run_generation, space.id, None)
    return to_detail(space)

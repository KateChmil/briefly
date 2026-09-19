from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ArtifactKind, ChatMessage, SpaceStatus
from ..schemas import ChatMessageOut, ChatRequest, ChatResponse
from ..services import agent, generation
from .spaces import get_space

router = APIRouter(prefix="/api/spaces/{space_id}", tags=["chat"])

PROFILE_FIELDS = {"goal", "exam_date", "level", "weekly_hours", "weak_topics", "notes"}


def clean_profile(data: dict, base: dict | None = None) -> dict:
    """Merge model-supplied profile fields into `base`, keeping only known keys."""
    merged = dict(base or {})
    for key, value in data.items():
        if key in PROFILE_FIELDS and value not in (None, "", []):
            merged[key] = value
    return merged


@router.get("/messages", response_model=list[ChatMessageOut])
def list_messages(space_id: str, db: Session = Depends(get_db)):
    get_space(db, space_id)
    return db.scalars(
        select(ChatMessage)
        .where(ChatMessage.space_id == space_id)
        .order_by(ChatMessage.id)
    ).all()


@router.post("/chat", response_model=ChatResponse)
def chat(
    space_id: str,
    req: ChatRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    space = get_space(db, space_id)
    if space.status == SpaceStatus.generating:
        raise HTTPException(
            status_code=409, detail="Still generating your materials — one moment."
        )

    user_msg = ChatMessage(space_id=space.id, role="user", content=req.content)
    db.add(user_msg)
    db.commit()
    history = [{"role": m.role, "content": m.content} for m in space.messages]

    profile_completed = plan_updating = False
    try:
        if space.status == SpaceStatus.interviewing:
            reply, profile = agent.run_interview_turn(space, history)
            kinds = None  # everything
            if profile is not None:
                space.profile = clean_profile(profile, space.profile)
                profile_completed = True
        else:
            reply, changes = agent.run_tutor_turn(space, history)
            kinds = [ArtifactKind.study_plan]
            if changes:
                space.profile = clean_profile(changes, space.profile)
                plan_updating = True
    except Exception as e:
        # Drop the unanswered message so the next attempt starts from clean history.
        db.rollback()
        db.delete(db.get(ChatMessage, user_msg.id))
        db.commit()
        detail = str(e) if isinstance(e, RuntimeError) else f"AI request failed: {e}"
        raise HTTPException(status_code=502, detail=detail)

    if profile_completed or plan_updating:
        space.status = SpaceStatus.generating
        background.add_task(generation.run_generation, space.id, kinds)

    msg = ChatMessage(space_id=space.id, role="assistant", content=reply)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return ChatResponse(
        message=ChatMessageOut.model_validate(msg),
        space_status=space.status.value,
        profile_completed=profile_completed,
        plan_updating=plan_updating,
    )

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ChatMessage, SpaceStatus
from ..schemas import ChatMessageOut, ChatRequest, ChatResponse
from ..services import agent, generation
from .spaces import get_space

router = APIRouter(prefix="/api/spaces/{space_id}", tags=["chat"])


@router.get("/messages", response_model=list[ChatMessageOut])
def list_messages(space_id: str, db: Session = Depends(get_db)):
    get_space(db, space_id)
    return db.scalars(
        select(ChatMessage)
        .where(ChatMessage.space_id == space_id)
        .order_by(ChatMessage.id)
    ).all()


@router.post("/chat", response_model=ChatResponse)
def chat(space_id: str, req: ChatRequest, db: Session = Depends(get_db)):
    space = get_space(db, space_id)
    db.add(ChatMessage(space_id=space.id, role="user", content=req.content))
    db.commit()

    history = [{"role": m.role, "content": m.content} for m in space.messages]
    profile_completed = False

    try:
        if space.status == SpaceStatus.interviewing:
            reply, profile = agent.run_interview_turn(space, history)
            if profile is not None:
                space.profile = profile
                space.status = SpaceStatus.generating
                db.commit()
                try:
                    generation.generate_all(db, space)
                finally:
                    space.status = SpaceStatus.ready
                    db.commit()
                profile_completed = True
        else:
            reply = agent.run_tutor_turn(space, history)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"AI request failed: {e}"
        )

    msg = ChatMessage(space_id=space.id, role="assistant", content=reply)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return ChatResponse(
        message=ChatMessageOut.model_validate(msg),
        space_status=space.status.value,
        profile_completed=profile_completed,
    )

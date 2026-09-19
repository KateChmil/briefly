from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CalendarEvent, space_exam_date
from ..schemas import ProgressOut, RescheduleResult, SessionOut
from ..services.catch_up import candidate_days, daily_minutes_cap, plan_catch_up
from .spaces import get_space

router = APIRouter(prefix="/api/spaces", tags=["catch-up"])


def _exam_days(db: Session) -> set[date]:
    """Days blocked for rescheduling: any exam event on the calendar."""
    return set(
        db.scalars(select(CalendarEvent.date).where(CalendarEvent.kind == "exam")).all()
    )


@router.get("/{space_id}/progress", response_model=ProgressOut)
def get_progress(space_id: str, db: Session = Depends(get_db)):
    space = get_space(db, space_id)
    today = date.today()
    sessions = list(space.sessions)
    exam = space_exam_date(space)
    busy = _exam_days(db)
    free_days = sum(1 for d in candidate_days(today, exam) if d not in busy)
    minutes_left = sum(s.minutes for s in sessions if not s.done)
    return ProgressOut(
        done=sum(1 for s in sessions if s.done),
        total=len(sessions),
        overdue=sum(1 for s in sessions if not s.done and s.date < today),
        minutes_left=minutes_left,
        on_track=minutes_left <= free_days * daily_minutes_cap(space.profile),
    )


@router.post("/{space_id}/sessions/reschedule", response_model=RescheduleResult)
def reschedule_sessions(space_id: str, db: Session = Depends(get_db)):
    space = get_space(db, space_id)
    sessions = list(space.sessions)  # ordered by date
    moved, unplaced = plan_catch_up(
        sessions,
        date.today(),
        space_exam_date(space),
        daily_minutes_cap(space.profile),
        _exam_days(db),
    )
    for session, new_date in moved:
        session.date = new_date
    db.commit()
    return RescheduleResult(
        sessions=[
            SessionOut.model_validate(s)
            for s in sorted(sessions, key=lambda s: s.date)
        ],
        moved=len(moved),
        unplaced=[SessionOut.model_validate(s) for s in unplaced],
    )

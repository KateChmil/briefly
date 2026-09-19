from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import CalendarEvent, StudySession, SubjectSpace, space_exam_date
from ..schemas import (
    CalendarItem,
    EventCreate,
    ImportResult,
    ImportUrlRequest,
    SessionOut,
    SessionPatch,
)
from ..services import ics
from .spaces import get_space

router = APIRouter(prefix="/api", tags=["calendar"])

MAX_IMPORT_EVENTS = 1500


def _sort_key(item: CalendarItem):
    return (item.date, item.start_time or "", item.type)


def build_items(
    db: Session, start: date, end: date, space_id: str | None = None
) -> list[CalendarItem]:
    spaces = {s.id: s for s in db.scalars(select(SubjectSpace))}
    items: list[CalendarItem] = []

    ev_query = select(CalendarEvent).where(CalendarEvent.date >= start, CalendarEvent.date <= end)
    if space_id:
        ev_query = ev_query.where(CalendarEvent.space_id == space_id)
    for e in db.scalars(ev_query):
        space = spaces.get(e.space_id) if e.space_id else None
        items.append(
            CalendarItem(
                id=f"event-{e.id}",
                type="event",
                date=e.date,
                start_time=e.start_time,
                end_time=e.end_time,
                title=e.title,
                kind=e.kind,
                space_id=e.space_id,
                space_name=space.name if space else None,
                topic=e.description or None,
                deletable=True,
            )
        )

    s_query = select(StudySession).where(StudySession.date >= start, StudySession.date <= end)
    if space_id:
        s_query = s_query.where(StudySession.space_id == space_id)
    for s in db.scalars(s_query):
        space = spaces.get(s.space_id)
        items.append(
            CalendarItem(
                id=f"session-{s.id}",
                type="session",
                date=s.date,
                title=s.title,
                kind=s.kind,
                space_id=s.space_id,
                space_name=space.name if space else None,
                done=s.done,
                minutes=s.minutes,
                topic=s.topic or None,
            )
        )

    for space in spaces.values():
        if space_id and space.id != space_id:
            continue
        exam = space_exam_date(space)
        if exam and start <= exam <= end:
            items.append(
                CalendarItem(
                    id=f"exam-{space.id}",
                    type="exam",
                    date=exam,
                    title=f"{space.name} exam",
                    kind="exam",
                    space_id=space.id,
                    space_name=space.name,
                )
            )
    return sorted(items, key=_sort_key)


@router.get("/calendar", response_model=list[CalendarItem])
def get_calendar(
    start: date | None = None,
    end: date | None = None,
    space_id: str | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    start = start or today - timedelta(days=30)
    end = end or today + timedelta(days=180)
    if end < start or (end - start).days > 800:
        raise HTTPException(status_code=422, detail="Invalid date range.")
    return build_items(db, start, end, space_id)


@router.post("/calendar/events", response_model=CalendarItem, status_code=201)
def create_event(req: EventCreate, db: Session = Depends(get_db)):
    space = get_space(db, req.space_id) if req.space_id else None
    event = CalendarEvent(
        space_id=req.space_id,
        title=req.title.strip(),
        date=req.date,
        start_time=req.start_time,
        end_time=req.end_time,
        kind=req.kind,
        description=req.description,
        source="manual",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return CalendarItem(
        id=f"event-{event.id}",
        type="event",
        date=event.date,
        start_time=event.start_time,
        end_time=event.end_time,
        title=event.title,
        kind=event.kind,
        space_id=event.space_id,
        space_name=space.name if space else None,
        topic=event.description or None,
        deletable=True,
    )


@router.delete("/calendar/events/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def patch_session(session_id: int, req: SessionPatch, db: Session = Depends(get_db)):
    session = db.get(StudySession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session.done = req.done
    db.commit()
    db.refresh(session)
    return session


def import_events(
    db: Session, text: str, space_id: str | None, source: str
) -> ImportResult:
    parsed = ics.parse_ics(text)
    if not parsed:
        raise HTTPException(status_code=422, detail="No events found in that calendar.")
    horizon_start = date.today() - timedelta(days=90)
    horizon_end = date.today() + timedelta(days=400)
    existing = {
        (e.external_uid, e.date, e.start_time)
        for e in db.scalars(select(CalendarEvent).where(CalendarEvent.source == source))
    }
    imported = skipped = 0
    for p in parsed:
        key = (p.uid, p.date, p.start_time)
        if not (horizon_start <= p.date <= horizon_end) or key in existing:
            skipped += 1
            continue
        if imported >= MAX_IMPORT_EVENTS:
            skipped += 1
            continue
        existing.add(key)
        db.add(
            CalendarEvent(
                space_id=space_id,
                title=p.title[:300],
                date=p.date,
                start_time=p.start_time,
                end_time=p.end_time,
                kind=p.kind,
                source=source,
                external_uid=p.uid[:300],
                description=p.description,
            )
        )
        imported += 1
    db.commit()
    return ImportResult(imported=imported, skipped=skipped)


@router.post("/calendar/import", response_model=ImportResult)
def import_ics_file(
    file: UploadFile = File(...),
    space_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if space_id:
        get_space(db, space_id)
    data = file.file.read(ics.MAX_FEED_BYTES + 1)
    if len(data) > ics.MAX_FEED_BYTES:
        raise HTTPException(status_code=413, detail="Calendar file is too large.")
    return import_events(db, data.decode("utf-8", errors="replace"), space_id, "ics")


@router.post("/calendar/import-url", response_model=ImportResult)
def import_ics_url(req: ImportUrlRequest, db: Session = Depends(get_db)):
    """Import a live calendar feed, e.g. the Canvas 'Calendar Feed' link."""
    if req.space_id:
        get_space(db, req.space_id)
    try:
        text = ics.fetch_ics(req.url)
    except ics.FeedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return import_events(db, text, req.space_id, "feed")


@dataclass
class _IcsItem:
    uid: str
    date: date
    start_time: str | None
    end_time: str | None
    title: str
    description: str


@router.get("/calendar/export.ics")
def export_ics(space_id: str | None = None, db: Session = Depends(get_db)):
    """Download study sessions and exams as an .ics file for Google/Outlook/Apple Calendar."""
    today = date.today()
    items = [
        _IcsItem(
            uid=i.id + (f"-{i.date}" if i.type == "exam" else ""),
            date=i.date,
            start_time=i.start_time,
            end_time=i.end_time,
            title=(f"{i.space_name}: " if i.space_name and i.type != "exam" else "") + i.title,
            description=" · ".join(
                x for x in (i.topic, f"{i.minutes} min" if i.minutes else None) if x
            ),
        )
        for i in build_items(db, today - timedelta(days=7), today + timedelta(days=400), space_id)
        if i.type in ("session", "exam") or space_id
    ]
    return Response(
        content=ics.build_ics(items),
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="briefly-plan.ics"'},
    )

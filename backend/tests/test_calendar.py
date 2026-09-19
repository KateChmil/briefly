from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services import ics

SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:exam-1@canvas
DTSTART;VALUE=DATE:20260930
SUMMARY:Calculus II Midterm
END:VEVENT
BEGIN:VEVENT
UID:lec-1@outlook
DTSTART;TZID=Europe/Budapest:20260921T100000
DTEND;TZID=Europe/Budapest:20260921T113000
SUMMARY:Biology 101 Lecture
DESCRIPTION:Room 4\\, building B\\nBring notes
RRULE:FREQ=WEEKLY;COUNT=3;BYDAY=MO
END:VEVENT
BEGIN:VEVENT
UID:folded
DTSTART:20261005T080000
SUMMARY:A very long title that is folded
  over two lines
END:VEVENT
BEGIN:VEVENT
UID:broken
SUMMARY:No start date
END:VEVENT
END:VCALENDAR
"""


def test_parse_ics_basic_events():
    events = ics.parse_ics(SAMPLE_ICS)
    by_uid = {}
    for e in events:
        by_uid.setdefault(e.uid, []).append(e)

    exam = by_uid["exam-1@canvas"][0]
    assert exam.date == date(2026, 9, 30)
    assert exam.kind == "exam" and exam.start_time is None

    folded = by_uid["folded"][0]
    assert folded.title == "A very long title that is folded over two lines"
    assert "broken" not in by_uid  # no DTSTART -> skipped


def test_parse_ics_weekly_recurrence_and_escapes():
    lectures = [e for e in ics.parse_ics(SAMPLE_ICS) if e.uid == "lec-1@outlook"]
    assert [e.date for e in lectures] == [date(2026, 9, 21), date(2026, 9, 28), date(2026, 10, 5)]
    assert all(e.start_time == "10:00" and e.end_time == "11:30" for e in lectures)
    assert lectures[0].kind == "class"
    assert lectures[0].description == "Room 4, building B\nBring notes"


def test_parse_ics_rrule_until_and_exdate():
    text = (
        "BEGIN:VEVENT\nUID:u\nDTSTART:20260921T100000\nSUMMARY:Lab\n"
        "RRULE:FREQ=WEEKLY;UNTIL=20261012T000000;BYDAY=MO\n"
        "EXDATE:20260928T100000\nEND:VEVENT"
    )
    assert [e.date for e in ics.parse_ics(text)] == [date(2026, 9, 21), date(2026, 10, 5)]


def test_build_ics_round_trips():
    item = SimpleNamespace(
        uid="session-1", date=date(2026, 10, 1), start_time=None, end_time=None,
        title="Biology: Review, part 1", description="cells.txt · 45 min",
    )
    text = ics.build_ics([item])
    assert "DTSTART;VALUE=DATE:20261001" in text
    back = ics.parse_ics(text)
    assert back[0].title == "Biology: Review, part 1"
    assert back[0].date == date(2026, 10, 1)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/feed.ics",  # not https
        "https://localhost/feed.ics",
        "https://127.0.0.1/feed.ics",
        "https://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
    ],
)
def test_fetch_ics_rejects_unsafe_urls(url):
    with pytest.raises(ics.FeedError):
        ics.fetch_ics(url)


# ---- API -------------------------------------------------------------------


def test_create_list_and_delete_event(client):
    soon = (date.today() + timedelta(days=3)).isoformat()
    r = client.post(
        "/api/calendar/events",
        json={"title": "Chemistry lecture", "date": soon, "start_time": "09:00", "end_time": "10:30", "kind": "class"},
    )
    assert r.status_code == 201
    item = r.json()
    assert item["type"] == "event" and item["deletable"] is True

    listed = client.get("/api/calendar").json()
    assert [i["title"] for i in listed] == ["Chemistry lecture"]

    assert client.delete(f"/api/calendar/events/{item['id'].split('-')[1]}").status_code == 204
    assert client.get("/api/calendar").json() == []


def test_event_validation(client):
    bad_time = client.post(
        "/api/calendar/events", json={"title": "x", "date": "2026-10-01", "start_time": "25:99"}
    )
    assert bad_time.status_code == 422
    no_space = client.post(
        "/api/calendar/events", json={"title": "x", "date": "2026-10-01", "space_id": "nope"}
    )
    assert no_space.status_code == 404


def test_import_ics_file_dedupes_and_lists(client):
    future = date.today() + timedelta(days=10)
    stamp = future.strftime("%Y%m%d")
    text = f"BEGIN:VEVENT\nUID:a\nDTSTART;VALUE=DATE:{stamp}\nSUMMARY:Physics final exam\nEND:VEVENT\n"
    files = {"file": ("cal.ics", text.encode(), "text/calendar")}
    r1 = client.post("/api/calendar/import", files=files)
    assert r1.status_code == 200 and r1.json() == {"imported": 1, "skipped": 0}
    r2 = client.post("/api/calendar/import", files={"file": ("cal.ics", text.encode(), "text/calendar")})
    assert r2.json() == {"imported": 0, "skipped": 1}  # same event is not duplicated

    items = client.get("/api/calendar").json()
    assert items[0]["title"] == "Physics final exam" and items[0]["kind"] == "exam"


def test_import_rejects_non_calendar_files(client):
    r = client.post("/api/calendar/import", files={"file": ("x.ics", b"hello", "text/calendar")})
    assert r.status_code == 422
    r = client.post("/api/calendar/import-url", json={"url": "https://127.0.0.1/x.ics"})
    assert r.status_code == 400


def test_calendar_merges_exam_sessions_and_events(client):
    from app.db import SessionLocal
    from app.models import StudySession, SubjectSpace

    exam = date.today() + timedelta(days=8)
    db = SessionLocal()
    space = SubjectSpace(name="Biology", profile={"goal": "pass", "exam_date": exam.isoformat()})
    db.add(space)
    db.flush()
    db.add(StudySession(space_id=space.id, date=date.today() + timedelta(days=2), title="Cells", minutes=45, kind="study"))
    db.commit()
    sid, session_id = space.id, db.query(StudySession).first().id
    db.close()

    items = client.get("/api/calendar").json()
    assert [(i["type"], i["title"]) for i in items] == [("session", "Cells"), ("exam", "Biology exam")]
    assert items[0]["space_name"] == "Biology"

    r = client.patch(f"/api/sessions/{session_id}", json={"done": True})
    assert r.status_code == 200 and r.json()["done"] is True
    assert client.get("/api/calendar", params={"space_id": sid}).json()[0]["done"] is True

    summary = client.get("/api/spaces").json()[0]
    assert summary["sessions_total"] == 1 and summary["sessions_done"] == 1
    assert summary["exam_date"] == exam.isoformat()


def test_export_ics(client):
    from app.db import SessionLocal
    from app.models import StudySession, SubjectSpace

    db = SessionLocal()
    space = SubjectSpace(name="Biology")
    db.add(space)
    db.flush()
    db.add(StudySession(space_id=space.id, date=date.today() + timedelta(days=1), title="Cells", minutes=30, kind="study"))
    db.commit()
    db.close()

    r = client.get("/api/calendar/export.ics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert "SUMMARY:Biology: Cells" in r.text
    assert "BEGIN:VCALENDAR" in r.text


def test_calendar_rejects_bad_range(client):
    assert client.get("/api/calendar", params={"start": "2026-10-10", "end": "2026-10-01"}).status_code == 422

from datetime import date, timedelta

from app.db import SessionLocal
from app.models import CalendarEvent, StudySession, SubjectSpace
from app.services.catch_up import daily_minutes_cap, plan_catch_up

TODAY = date(2026, 3, 10)


def d(n: int) -> date:
    return TODAY + timedelta(days=n)


class FakeSession:
    def __init__(self, offset, minutes=45, done=False):
        self.date = d(offset)
        self.minutes = minutes
        self.done = done
        self.title = f"s{offset}"


def moved_dates(moved):
    return [(s.title, day) for s, day in moved]


def test_no_overdue_sessions_moves_nothing():
    moved, unplaced = plan_catch_up(
        [FakeSession(1), FakeSession(3)], TODAY, d(10), 90, set()
    )
    assert moved == [] and unplaced == []


def test_done_sessions_are_never_moved():
    sessions = [FakeSession(-2, done=True), FakeSession(-1)]
    moved, unplaced = plan_catch_up(sessions, TODAY, d(10), 90, set())
    assert moved_dates(moved) == [("s-1", d(1))]
    assert unplaced == []
    assert sessions[0].date == d(-2)  # untouched


def test_exam_tomorrow_leaves_everything_unplaced():
    moved, unplaced = plan_catch_up(
        [FakeSession(-1), FakeSession(-2)], TODAY, d(1), 90, set()
    )
    assert moved == [] and len(unplaced) == 2


def test_daily_cap_exhaustion_goes_to_unplaced():
    # cap 60, two 45-min sessions, only tomorrow free before the exam
    moved, unplaced = plan_catch_up(
        [FakeSession(-2, 45), FakeSession(-1, 45)], TODAY, d(2), 60, set()
    )
    assert moved_dates(moved) == [("s-2", d(1))]
    assert [s.title for s in unplaced] == ["s-1"]


def test_exam_event_day_is_skipped():
    moved, _ = plan_catch_up([FakeSession(-1)], TODAY, d(4), 90, {d(1)})
    assert moved_dates(moved) == [("s-1", d(2))]


def test_original_order_is_kept():
    sessions = [FakeSession(-1), FakeSession(-3), FakeSession(-2)]
    moved, _ = plan_catch_up(sessions, TODAY, d(10), 60, set())
    assert [s.title for s, _ in moved] == ["s-1", "s-3", "s-2"]
    assert [day for _, day in moved] == [d(1), d(2), d(3)]


def test_sessions_already_on_a_day_count_toward_the_cap():
    # tomorrow already holds a 30-min session; a 45-min one would exceed 60
    moved, _ = plan_catch_up(
        [FakeSession(-1, 45), FakeSession(1, 30)], TODAY, d(5), 60, set()
    )
    assert moved_dates(moved) == [("s-1", d(2))]


def test_no_exam_uses_fourteen_day_horizon():
    moved, unplaced = plan_catch_up([FakeSession(-1)], TODAY, None, 60, set())
    assert moved_dates(moved) == [("s-1", d(1))] and unplaced == []
    # a session longer than the daily cap never fits, even without an exam
    moved2, unplaced2 = plan_catch_up([FakeSession(-1, 120)], TODAY, None, 60, set())
    assert moved2 == [] and len(unplaced2) == 1


def test_daily_minutes_cap():
    assert daily_minutes_cap({"weekly_hours": 7}) == 60
    assert daily_minutes_cap({"weekly_hours": 14}) == 120
    assert daily_minutes_cap({}) == 90
    assert daily_minutes_cap(None) == 90
    assert daily_minutes_cap({"weekly_hours": "abc"}) == 90


# --- API endpoints -------------------------------------------------------


def _space_with_past_sessions(db, exam_in=10, weekly_hours=7):
    today = date.today()
    space = SubjectSpace(
        name="Bio",
        profile={
            "weekly_hours": weekly_hours,
            "exam_date": (today + timedelta(days=exam_in)).isoformat(),
        },
    )
    db.add(space)
    db.flush()
    for offset, minutes, done in ((-2, 45, False), (-1, 30, False), (3, 45, True)):
        db.add(
            StudySession(
                space_id=space.id,
                date=today + timedelta(days=offset),
                title=f"s{offset}",
                topic="",
                minutes=minutes,
                kind="study",
                done=done,
            )
        )
    db.commit()
    return space, today


def test_reschedule_endpoint(client):
    db = SessionLocal()
    space, today = _space_with_past_sessions(db)
    db.close()

    r = client.post(f"/api/spaces/{space.id}/sessions/reschedule")
    assert r.status_code == 200
    data = r.json()
    assert data["moved"] == 2 and data["unplaced"] == []
    dates = {s["title"]: s["date"] for s in data["sessions"]}
    # weekly_hours 7 -> cap 60/day: 45-min then 30-min sessions land on separate days
    assert dates["s-2"] == (today + timedelta(days=1)).isoformat()
    assert dates["s-1"] == (today + timedelta(days=2)).isoformat()
    assert dates["s3"] == (today + timedelta(days=3)).isoformat()  # done: unmoved


def test_reschedule_skips_exam_event_days(client):
    db = SessionLocal()
    space, today = _space_with_past_sessions(db)
    db.add(
        CalendarEvent(
            space_id=space.id,
            title="Other exam",
            date=today + timedelta(days=1),
            kind="exam",
            source="manual",
        )
    )
    db.commit()
    db.close()

    data = client.post(f"/api/spaces/{space.id}/sessions/reschedule").json()
    dates = {s["title"]: s["date"] for s in data["sessions"]}
    assert dates["s-2"] == (today + timedelta(days=2)).isoformat()


def test_reschedule_missing_space(client):
    assert client.post("/api/spaces/nope/sessions/reschedule").status_code == 404


def test_progress_endpoint(client):
    db = SessionLocal()
    space, _ = _space_with_past_sessions(db)
    db.close()

    data = client.get(f"/api/spaces/{space.id}/progress").json()
    assert data == {
        "done": 1,
        "total": 3,
        "overdue": 2,
        "minutes_left": 75,
        "on_track": True,
    }

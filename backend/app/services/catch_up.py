"""Deterministic catch-up rescheduling — pure logic, no AI call.

When a student falls behind, undone sessions dated before `today` are moved
onto the next free days (starting tomorrow) before the exam.
"""

from collections.abc import Iterable, Iterator
from datetime import date, timedelta
from typing import Protocol, TypeVar

DEFAULT_DAILY_CAP = 90
MIN_DAILY_CAP = 60
FALLBACK_HORIZON_DAYS = 14


class SessionLike(Protocol):
    date: date
    minutes: int
    done: bool


S = TypeVar("S", bound=SessionLike)


def daily_minutes_cap(profile: dict | None) -> int:
    """Per-day study budget: weekly_hours / 7, at least 60 min; 90 if unknown."""
    try:
        hours = float((profile or {}).get("weekly_hours"))
    except (TypeError, ValueError):
        return DEFAULT_DAILY_CAP
    return max(MIN_DAILY_CAP, round(hours * 60 / 7))


def candidate_days(today: date, exam_date: date | None) -> Iterator[date]:
    """Reschedulable days: tomorrow until the day before the exam.

    With no exam date, the next 14 days.
    """
    end = exam_date or (today + timedelta(days=FALLBACK_HORIZON_DAYS + 1))
    d = today + timedelta(days=1)
    while d < end:
        yield d
        d += timedelta(days=1)


def plan_catch_up(
    sessions: Iterable[S],
    today: date,
    exam_date: date | None,
    daily_cap: int,
    busy_days: set[date] | frozenset[date] = frozenset(),
) -> tuple[list[tuple[S, date]], list[S]]:
    """Move undone sessions dated before `today` forward.

    Returns (moved, unplaced): `moved` is a list of (session, new_date) pairs,
    `unplaced` the sessions that did not fit before the exam.

    Rules: original order is kept; a day's total undone minutes never exceeds
    `daily_cap` (sessions already scheduled on a day count towards it); nothing
    lands on `today`, on/after `exam_date`, or on a `busy_days` date; done
    sessions are never moved.
    """
    sessions = list(sessions)
    overdue = [s for s in sessions if not s.done and s.date < today]

    load: dict[date, int] = {}
    for s in sessions:
        if not s.done and s.date >= today:
            load[s.date] = load.get(s.date, 0) + s.minutes

    moved: list[tuple[S, date]] = []
    unplaced: list[S] = []
    for s in overdue:
        for d in candidate_days(today, exam_date):
            if d in busy_days:
                continue
            if load.get(d, 0) + s.minutes <= daily_cap:
                load[d] = load.get(d, 0) + s.minutes
                moved.append((s, d))
                break
        else:
            unplaced.append(s)
    return moved, unplaced

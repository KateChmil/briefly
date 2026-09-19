"""Minimal iCalendar (.ics) support: parse feeds from Canvas/Outlook/Google, export plans."""

import ipaddress
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_OCCURRENCES = 200
EXAM_WORDS = re.compile(
    r"\b(exam|test|quiz|midterm|final|assessment|colloquium|vizsga|zh|dolgozat)\b",
    re.IGNORECASE,
)
CLASS_WORDS = re.compile(
    r"\b(lecture|class|seminar|lab|tutorial|practice|workshop|előadás|gyakorlat)\b",
    re.IGNORECASE,
)
DAY_NAMES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


@dataclass
class ParsedEvent:
    uid: str
    title: str
    date: date
    start_time: str | None
    end_time: str | None
    description: str
    kind: str


def guess_kind(title: str) -> str:
    if EXAM_WORDS.search(title):
        return "exam"
    if CLASS_WORDS.search(title):
        return "class"
    return "other"


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _parse_dt(value: str) -> tuple[datetime | date, bool] | None:
    """Return (value, is_all_day). UTC timestamps are converted to local time."""
    value = value.strip()
    try:
        if len(value) == 8:
            return datetime.strptime(value, "%Y%m%d").date(), True
        if value.endswith("Z"):
            dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            return dt.astimezone().replace(tzinfo=None), False
        return datetime.strptime(value[:15], "%Y%m%dT%H%M%S"), False
    except ValueError:
        return None


def _day_of(value: datetime | date) -> date:
    return value.date() if isinstance(value, datetime) else value


def _after(occ: datetime | date, until: datetime | date) -> bool:
    """Is `occ` past the RRULE UNTIL bound? Compares exact times when both have them."""
    if isinstance(occ, datetime) and isinstance(until, datetime):
        return occ > until
    return _day_of(occ) > _day_of(until)


def _expand(start: datetime | date, rrule: str, exdates: set[date]):
    """Yield occurrence starts. Supports DAILY/WEEKLY with INTERVAL/COUNT/UNTIL/BYDAY."""
    parts = dict(p.split("=", 1) for p in rrule.split(";") if "=" in p)
    freq = parts.get("FREQ")
    if freq not in ("DAILY", "WEEKLY"):
        yield start
        return
    interval = max(int(parts["INTERVAL"]), 1) if parts.get("INTERVAL", "").isdigit() else 1
    count = int(parts["COUNT"]) if parts.get("COUNT", "").isdigit() else MAX_OCCURRENCES
    count = min(count, MAX_OCCURRENCES)
    until = None
    if "UNTIL" in parts:
        parsed = _parse_dt(parts["UNTIL"])
        until = parsed[0] if parsed else None
    horizon = date.today() + timedelta(days=365)
    start_day = _day_of(start)

    if freq == "DAILY":
        offsets = [i * interval for i in range(count)]
    else:
        byday = [d[-2:] for d in parts.get("BYDAY", "").split(",") if d]
        weekdays = sorted(DAY_NAMES.index(d) for d in byday if d in DAY_NAMES) or [
            start_day.weekday()
        ]
        week0 = start_day - timedelta(days=start_day.weekday())
        offsets = sorted(
            off
            for w in range(MAX_OCCURRENCES)
            for wd in weekdays
            if (off := (week0 + timedelta(weeks=w * interval, days=wd) - start_day).days) >= 0
        )

    emitted = 0
    for off in offsets:
        if emitted >= count:
            return
        occ = start + timedelta(days=off)
        occ_day = _day_of(occ)
        if occ_day > horizon or (until is not None and _after(occ, until)):
            return
        emitted += 1
        if occ_day not in exdates:
            yield occ


def parse_ics(text: str) -> list[ParsedEvent]:
    events: list[ParsedEvent] = []
    props: dict[str, list[str]] | None = None
    for line in _unfold(text):
        upper = line.strip().upper()
        if upper == "BEGIN:VEVENT":
            props = {}
            continue
        if upper == "END:VEVENT":
            if props is not None:
                events.extend(_build_events(props))
            props = None
            continue
        if props is None or ":" not in line:
            continue
        head, value = line.split(":", 1)
        name = head.split(";", 1)[0].upper()
        props.setdefault(name, []).append(value)
    return events


def _build_events(props: dict[str, list[str]]) -> list[ParsedEvent]:
    if "DTSTART" not in props:
        return []
    parsed = _parse_dt(props["DTSTART"][0])
    if not parsed:
        return []
    start = parsed[0]
    end = None
    if "DTEND" in props:
        e = _parse_dt(props["DTEND"][0])
        end = e[0] if e else None
    duration = end - start if isinstance(start, datetime) and isinstance(end, datetime) else None

    title = _unescape(props.get("SUMMARY", ["Untitled event"])[0]).strip() or "Untitled event"
    description = _unescape(props.get("DESCRIPTION", [""])[0]).strip()[:1000]
    uid = props.get("UID", [title])[0].strip()
    kind = guess_kind(title)

    exdates: set[date] = set()
    for value in props.get("EXDATE", []):
        for piece in value.split(","):
            p = _parse_dt(piece)
            if p:
                exdates.add(_day_of(p[0]))

    rrule = props.get("RRULE", [""])[0]
    occurrences = _expand(start, rrule, exdates) if rrule else [start]

    out = []
    for occ in occurrences:
        if isinstance(occ, datetime):
            start_time = occ.strftime("%H:%M")
            end_time = (occ + duration).strftime("%H:%M") if duration else None
        else:
            start_time, end_time = None, None
        out.append(ParsedEvent(uid, title, _day_of(occ), start_time, end_time, description, kind))
    return out


class FeedError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch_ics(url: str) -> str:
    """Download an ICS feed (e.g. a Canvas calendar feed) with basic SSRF protection."""
    url = url.strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://") :]
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise FeedError("Calendar feed URL must start with https:// (or webcal://).")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror:
        raise FeedError("Could not resolve the calendar feed host.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise FeedError("That address is not allowed.")
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "Briefly"})
    try:
        with opener.open(request, timeout=10) as r:
            data = r.read(MAX_FEED_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise FeedError(f"Calendar feed returned HTTP {e.code}.")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise FeedError("Could not download the calendar feed.")
    if len(data) > MAX_FEED_BYTES:
        raise FeedError("Calendar feed is too large.")
    return data.decode("utf-8", errors="replace")


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def build_ics(items) -> str:
    """Build an ICS file. `items` need uid, date, start_time, end_time, title, description."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Briefly//Study Planner//EN",
        "CALSCALE:GREGORIAN",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for it in items:
        lines += ["BEGIN:VEVENT", f"UID:{it.uid}@briefly", f"DTSTAMP:{stamp}"]
        if it.start_time:
            start = datetime.combine(it.date, datetime.strptime(it.start_time, "%H:%M").time())
            lines.append(f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}")
            if it.end_time:
                end = datetime.combine(it.date, datetime.strptime(it.end_time, "%H:%M").time())
                lines.append(f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{it.date.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{(it.date + timedelta(days=1)).strftime('%Y%m%d')}")
        lines.append(f"SUMMARY:{_escape(it.title)}")
        if it.description:
            lines.append(f"DESCRIPTION:{_escape(it.description)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

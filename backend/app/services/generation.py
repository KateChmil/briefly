"""Generate a space's study plan, notes, sample test and flashcards with Claude.

The plan, test and flashcards are requested through forced tool calls so the
model returns structured data; everything is validated before it is stored, and
each artifact is retried once if the model returns something unusable.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import (
    Artifact,
    ArtifactKind,
    CalendarEvent,
    ChatMessage,
    SpaceStatus,
    StudySession,
    SubjectSpace,
    space_exam_date,
)
from .agent import text_of
from .llm import create_message, tool_input

log = logging.getLogger(__name__)

ALL_KINDS = list(ArtifactKind)
LABELS = {
    ArtifactKind.study_plan: "study plan",
    ArtifactKind.notes: "notes",
    ArtifactKind.sample_test: "sample test",
    ArtifactKind.flashcards: "flashcards",
}
DEFAULT_HORIZON_DAYS = 28
MAX_SESSIONS = 120


class GenerationError(Exception):
    """The model's output could not be turned into a usable artifact."""


# --------------------------------------------------------------------------
# Prompts and tool schemas
# --------------------------------------------------------------------------

PLAN_PROMPT = """You are an expert study coach. Using the student profile, calendar and course materials provided, build a concrete study plan by calling submit_study_plan.

- `overview`: Markdown with the strategy, weekly milestones and study tips. Keep it under 300 words.
- `sessions`: individual dated study blocks between today and the exam date (or the next 4 weeks if there is no exam date).
  - Size the total minutes per week to the student's weekly hours.
  - Prefer varied days, avoid the calendar events listed, and don't schedule more than one block per day unless the timeline is very short.
  - Reference the attached sources by filename in `topic` where relevant, and prioritise the student's weak topics.
  - Use kind "practice" and "review" regularly and finish with a "mock_exam" a few days before the exam.
  - Each block is 20-120 minutes. Use ISO dates (YYYY-MM-DD)."""

NOTES_PROMPT = """You are an expert note-taker. Condense the attached course materials into clear, well-structured study notes in Markdown.

Cover key concepts, definitions, formulas and must-remember facts, organized by topic with headings and bullet points. Prioritize topics the student marked as weak. Output Markdown only."""

TEST_PROMPT = """You are an exam writer. Create a sample test for the subject based on the attached materials and student profile by calling submit_sample_test.

Write 8-12 questions of mixed difficulty, weighted toward the student's weak topics. For "mcq" questions give 3-4 choices and set "answer" to exactly one of the choices. For "short" questions, "answer" is a concise model answer. Always include a short explanation."""

CARDS_PROMPT = """You are a flashcard author. From the attached course materials, create 12-20 flashcards by calling submit_flashcards.

Each card tests one atomic fact, definition, formula or concept: a short question or term on the front and a concise answer on the back. Prioritize the student's weak topics."""

PLAN_TOOL = {
    "name": "submit_study_plan",
    "description": "Submit the finished study plan.",
    "input_schema": {
        "type": "object",
        "properties": {
            "overview": {"type": "string"},
            "sessions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "YYYY-MM-DD"},
                        "title": {"type": "string"},
                        "topic": {"type": "string"},
                        "minutes": {"type": "integer"},
                        "kind": {
                            "type": "string",
                            "enum": ["study", "review", "practice", "mock_exam"],
                        },
                    },
                    "required": ["date", "title", "minutes", "kind"],
                },
            },
        },
        "required": ["overview", "sessions"],
    },
}

TEST_TOOL = {
    "name": "submit_sample_test",
    "description": "Submit the finished sample test.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["mcq", "short"]},
                        "question": {"type": "string"},
                        "choices": {"type": "array", "items": {"type": "string"}},
                        "answer": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["type", "question", "answer", "explanation"],
                },
            },
        },
        "required": ["title", "questions"],
    },
}

CARDS_TOOL = {
    "name": "submit_flashcards",
    "description": "Submit the finished flashcards.",
    "input_schema": {
        "type": "object",
        "properties": {
            "cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "front": {"type": "string"},
                        "back": {"type": "string"},
                    },
                    "required": ["front", "back"],
                },
            }
        },
        "required": ["cards"],
    },
}


# --------------------------------------------------------------------------
# Validation of model output
# --------------------------------------------------------------------------


class PlanSession(BaseModel):
    date: date
    title: str
    topic: str = ""
    minutes: int = 45
    kind: Literal["study", "review", "practice", "mock_exam"] = "study"

    @field_validator("kind", mode="before")
    @classmethod
    def _known_kind(cls, v):
        return v if v in ("study", "review", "practice", "mock_exam") else "study"

    @field_validator("minutes", mode="before")
    @classmethod
    def _clamp_minutes(cls, v):
        try:
            return min(max(int(v), 10), 300)
        except (TypeError, ValueError):
            return 45


def parse_plan(raw: dict, today: date, exam: date | None) -> dict:
    last_day = exam or today + timedelta(days=DEFAULT_HORIZON_DAYS)
    sessions = []
    for item in raw.get("sessions") or []:
        try:
            s = PlanSession.model_validate(item)
        except ValidationError:
            continue
        if s.title.strip() and today <= s.date <= last_day:
            sessions.append(s)
    if not sessions:
        raise GenerationError("the plan contained no usable dated sessions")
    sessions.sort(key=lambda s: s.date)
    return {
        "overview": str(raw.get("overview") or "").strip(),
        "sessions": [
            {**s.model_dump(), "date": s.date.isoformat()} for s in sessions[:MAX_SESSIONS]
        ],
    }


def _match_choice(answer: str, choices: list[str]) -> str | None:
    a = answer.strip()
    for c in choices:
        if c == a:
            return c
    for c in choices:
        if c.strip().lower() == a.lower():
            return c
    letter = a.rstrip(").:").upper()
    if len(letter) == 1 and "A" <= letter <= "F" and ord(letter) - 65 < len(choices):
        return choices[ord(letter) - 65]
    return None


def parse_quiz(raw: dict) -> dict:
    questions = []
    for q in raw.get("questions") or []:
        if not isinstance(q, dict):
            continue
        question = str(q.get("question") or "").strip()
        answer = str(q.get("answer") or "").strip()
        if not question or not answer:
            continue
        explanation = str(q.get("explanation") or "").strip()
        if q.get("type") == "mcq":
            choices = list(dict.fromkeys(str(c).strip() for c in q.get("choices") or [] if str(c).strip()))
            matched = _match_choice(answer, choices) if len(choices) >= 2 else None
            if matched is None:
                continue
            questions.append(
                {"type": "mcq", "question": question, "choices": choices,
                 "answer": matched, "explanation": explanation}
            )
        else:
            questions.append(
                {"type": "short", "question": question, "answer": answer,
                 "explanation": explanation}
            )
    if len(questions) < 3:
        raise GenerationError("the sample test had too few valid questions")
    return {"title": str(raw.get("title") or "Sample test").strip(), "questions": questions}


def parse_cards(raw: dict) -> dict:
    cards = []
    for c in raw.get("cards") or []:
        if not isinstance(c, dict):
            continue
        front, back = str(c.get("front") or "").strip(), str(c.get("back") or "").strip()
        if front and back:
            cards.append({"front": front, "back": back})
    if len(cards) < 4:
        raise GenerationError("too few valid flashcards")
    return {"cards": cards}


# --------------------------------------------------------------------------
# Context building
# --------------------------------------------------------------------------


def build_context(
    space: SubjectSpace, events=(), today: date | None = None
) -> str:
    import json

    today = today or date.today()
    parts = [f"Today's date: {today.isoformat()}", f"Subject: {space.name}"]
    if space.profile:
        parts.append("Student profile:\n" + json.dumps(space.profile, indent=2))
    if events:
        lines = []
        for e in events:
            when = f"{e.date.isoformat()} {e.start_time or ''}".strip()
            lines.append(f"- {when} {e.title} ({e.kind})")
        parts.append("Calendar (avoid clashes):\n" + "\n".join(lines))
    for src in space.sources:
        text = src.extracted_text or ""
        if len(text) > settings.max_source_chars:
            half = settings.max_source_chars // 2
            text = text[:half] + "\n...[truncated]...\n" + text[-half:]
        parts.append(f"--- Source: {src.filename} ---\n{text}")
    if len(space.sources) == 0:
        parts.append("No source files attached; rely on the student profile.")
    return "\n\n".join(parts)[: settings.total_context_chars]


def load_events(db: Session, space: SubjectSpace, today: date | None = None):
    today = today or date.today()
    return db.scalars(
        select(CalendarEvent)
        .where(
            (CalendarEvent.space_id == space.id) | (CalendarEvent.space_id.is_(None)),
            CalendarEvent.date >= today,
            CalendarEvent.date <= today + timedelta(days=60),
        )
        .order_by(CalendarEvent.date, CalendarEvent.start_time)
        .limit(40)
    ).all()


# --------------------------------------------------------------------------
# Generation (pure: no database access, safe to run in threads)
# --------------------------------------------------------------------------


@dataclass
class Generated:
    content: str
    format: str
    sessions: list[dict] | None = None


def _structured(system, context, tool, parser, client, max_tokens=4096):
    """Force a tool call, validate the result, and retry once if it is unusable."""
    last_error = "the model did not return structured output"
    for _ in range(2):
        resp = create_message(
            system=system,
            messages=[{"role": "user", "content": context}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            max_tokens=max_tokens,
            client=client,
        )
        raw = tool_input(resp, tool["name"])
        if raw is None:
            continue
        try:
            return parser(raw)
        except GenerationError as e:
            last_error = str(e)
    raise GenerationError(last_error)


def generate_artifact(
    context: str,
    kind: ArtifactKind,
    *,
    exam_date: date | None = None,
    today: date | None = None,
    client=None,
) -> Generated:
    import json

    today = today or date.today()
    if kind == ArtifactKind.notes:
        resp = create_message(
            system=NOTES_PROMPT,
            messages=[{"role": "user", "content": context}],
            client=client,
        )
        text = text_of(resp.content).strip()
        if not text:
            raise GenerationError("the notes came back empty")
        return Generated(text, "markdown")
    if kind == ArtifactKind.study_plan:
        plan = _structured(
            PLAN_PROMPT, context, PLAN_TOOL,
            lambda raw: parse_plan(raw, today, exam_date), client, max_tokens=8000,
        )
        return Generated(json.dumps(plan, indent=2), "json", plan["sessions"])
    if kind == ArtifactKind.sample_test:
        quiz = _structured(TEST_PROMPT, context, TEST_TOOL, parse_quiz, client)
        return Generated(json.dumps(quiz, indent=2), "json")
    cards = _structured(CARDS_PROMPT, context, CARDS_TOOL, parse_cards, client)
    return Generated(json.dumps(cards, indent=2), "json")


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


def _next_version(db: Session, space_id: str, kind: ArtifactKind) -> int:
    current = db.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.space_id == space_id, Artifact.kind == kind
        )
    )
    return (current or 0) + 1


def replace_sessions(db: Session, space_id: str, sessions: list[dict]) -> None:
    """Swap the space's study sessions for a new plan, keeping ticks on identical ones."""
    old = db.scalars(select(StudySession).where(StudySession.space_id == space_id)).all()
    done = {(s.date.isoformat(), s.title) for s in old if s.done}
    for s in old:
        db.delete(s)
    db.flush()
    for s in sessions:
        db.add(
            StudySession(
                space_id=space_id,
                date=date.fromisoformat(s["date"]),
                title=s["title"][:200],
                topic=(s.get("topic") or "")[:300],
                minutes=s["minutes"],
                kind=s["kind"],
                done=(s["date"], s["title"]) in done,
            )
        )


def save_artifact(db: Session, space_id: str, kind: ArtifactKind, gen: Generated) -> Artifact:
    artifact = Artifact(
        space_id=space_id,
        kind=kind,
        format=gen.format,
        content=gen.content,
        version=_next_version(db, space_id, kind),
    )
    db.add(artifact)
    if gen.sessions is not None:
        replace_sessions(db, space_id, gen.sessions)
    db.commit()
    db.refresh(artifact)
    return artifact


def describe_error(e: Exception) -> str:
    if isinstance(e, (GenerationError, RuntimeError)):
        return str(e)
    return f"{type(e).__name__}: {str(e)[:150]}"


def regenerate_one(db: Session, space: SubjectSpace, kind: ArtifactKind, client=None) -> Artifact:
    """Generate and store one artifact synchronously (used by the Regenerate button)."""
    context = build_context(space, load_events(db, space))
    gen = generate_artifact(context, kind, exam_date=space_exam_date(space), client=client)
    return save_artifact(db, space.id, kind, gen)


def run_generation(space_id: str, kinds: list[ArtifactKind] | None = None, client=None) -> None:
    """Background job: generate `kinds` in parallel and save each as soon as it is ready.

    Opens its own database session. When it finishes the space is `ready` if any
    artifact exists (otherwise back to `interviewing`, keeping the saved profile so
    the student can retry), and a chat message explains anything that failed.
    """
    kinds = kinds or ALL_KINDS
    db = SessionLocal()
    try:
        space = db.get(SubjectSpace, space_id)
        if space is None:
            return
        context = build_context(space, load_events(db, space))
        exam = space_exam_date(space)
        errors: dict[ArtifactKind, str] = {}

        with ThreadPoolExecutor(max_workers=len(kinds)) as pool:
            futures = {
                pool.submit(generate_artifact, context, k, exam_date=exam, client=client): k
                for k in kinds
            }
            for fut in as_completed(futures):
                kind = futures[fut]
                try:
                    save_artifact(db, space_id, kind, fut.result())
                except Exception as e:  # keep going: partial results are still useful
                    log.warning("Generating %s failed: %s", kind.value, e)
                    db.rollback()
                    errors[kind] = describe_error(e)

        has_any = db.scalar(select(func.count(Artifact.id)).where(Artifact.space_id == space_id))
        space.status = SpaceStatus.ready if has_any else SpaceStatus.interviewing
        if errors:
            names = ", ".join(LABELS[k] for k in kinds if k in errors)
            reason = next(iter(errors.values()))
            db.add(
                ChatMessage(
                    space_id=space_id,
                    role="assistant",
                    content=(
                        f"⚠️ I couldn't finish your {names} ({reason}). "
                        "Use the **Generate** / **Regenerate** button to try again."
                    ),
                )
            )
        db.commit()
    except Exception:
        log.exception("Generation job crashed for space %s", space_id)
        db.rollback()
        space = db.get(SubjectSpace, space_id)
        if space is not None:
            space.status = SpaceStatus.interviewing
            db.commit()
    finally:
        db.close()


def recover_stuck_spaces() -> None:
    """After a restart, spaces left in `generating` can never finish: unstick them."""
    db = SessionLocal()
    try:
        for space in db.scalars(
            select(SubjectSpace).where(SubjectSpace.status == SpaceStatus.generating)
        ):
            has_any = db.scalar(select(func.count(Artifact.id)).where(Artifact.space_id == space.id))
            space.status = SpaceStatus.ready if has_any else SpaceStatus.interviewing
        db.commit()
    finally:
        db.close()

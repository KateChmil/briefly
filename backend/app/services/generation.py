import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Artifact, ArtifactKind, SubjectSpace
from .agent import text_of
from .llm import create_message

PLAN_PROMPT = """You are an expert study coach. Using the student profile and course materials provided, write a concrete study plan in Markdown.

Include:
- A week-by-week schedule (or day-by-day if the timeline is short), sized to the student's available weekly hours and exam date.
- What to review or practice each session, referencing the attached sources by filename.
- Regular checkpoints and self-testing days.

Keep it realistic and actionable. Output Markdown only."""

NOTES_PROMPT = """You are an expert note-taker. Condense the attached course materials into clear, well-structured study notes in Markdown.

Cover key concepts, definitions, formulas and must-remember facts, organized by topic. Prioritize topics the student marked as weak. Output Markdown only."""

TEST_PROMPT = """You are an exam writer. Create a sample test for the subject based on the attached materials and student profile.

Output ONLY valid JSON (no markdown fences, no commentary) with this shape:
{
  "title": "string",
  "questions": [
    {"type": "mcq", "question": "string", "choices": ["a", "b", "c", "d"], "answer": "string", "explanation": "string"},
    {"type": "short", "question": "string", "answer": "string", "explanation": "string"}
  ]
}

Rules: 8-12 questions, mixed difficulty, weighted toward the student's weak topics. For "mcq" questions, "answer" must exactly match one of the choices. For "short" questions, "answer" is a concise model answer."""

PROMPTS = {
    ArtifactKind.study_plan: PLAN_PROMPT,
    ArtifactKind.notes: NOTES_PROMPT,
    ArtifactKind.sample_test: TEST_PROMPT,
}


def build_context(space: SubjectSpace) -> str:
    parts = [f"Subject: {space.name}"]
    if space.profile:
        parts.append(
            "Student profile:\n" + json.dumps(space.profile, indent=2)
        )
    for src in space.sources:
        text = src.extracted_text or ""
        if len(text) > settings.max_source_chars:
            half = settings.max_source_chars // 2
            text = text[:half] + "\n...[truncated]...\n" + text[-half:]
        parts.append(f"--- Source: {src.filename} ---\n{text}")
    if len(space.sources) == 0:
        parts.append("No source files attached; rely on the student profile.")
    return "\n\n".join(parts)[: settings.total_context_chars]


def _parse_json(text: str) -> str | None:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    candidates = [t]
    if "{" in t and "}" in t:
        candidates.append(t[t.find("{") : t.rfind("}") + 1])
    for c in candidates:
        try:
            return json.dumps(json.loads(c), indent=2)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def generate_one(
    space: SubjectSpace, kind: ArtifactKind, client=None
) -> tuple[str, str]:
    """Generate a single artifact. Returns (content, format)."""
    resp = create_message(
        system=PROMPTS[kind],
        messages=[{"role": "user", "content": build_context(space)}],
        client=client,
    )
    text = text_of(resp.content)
    if kind == ArtifactKind.sample_test:
        parsed = _parse_json(text)
        if parsed is not None:
            return parsed, "json"
    return text, "markdown"


def _next_version(db: Session, space: SubjectSpace, kind: ArtifactKind) -> int:
    current = db.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.space_id == space.id, Artifact.kind == kind
        )
    )
    return (current or 0) + 1


def generate_all(db: Session, space: SubjectSpace, client=None) -> None:
    for kind in ArtifactKind:
        content, fmt = generate_one(space, kind, client=client)
        db.add(
            Artifact(
                space_id=space.id,
                kind=kind,
                format=fmt,
                content=content,
                version=_next_version(db, space, kind),
            )
        )
    db.commit()

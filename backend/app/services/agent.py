import json
from datetime import date

from ..config import settings
from ..models import SubjectSpace
from .llm import create_message
from .retrieval import select_excerpts

_PROFILE_PROPERTIES = {
    "goal": {
        "type": "string",
        "description": "What the student is working toward",
    },
    "exam_date": {
        "type": "string",
        "description": (
            "Exam/deadline date as ISO YYYY-MM-DD (resolve phrases like 'next "
            "Friday' using today's date). Omit if the student has no date."
        ),
    },
    "level": {
        "type": "string",
        "description": "e.g. beginner / intermediate / advanced",
    },
    "weekly_hours": {
        "type": "number",
        "description": "Hours per week the student can study",
    },
    "weak_topics": {
        "type": "array",
        "items": {"type": "string"},
    },
    "notes": {
        "type": "string",
        "description": "Anything else relevant the student mentioned",
    },
}

PROFILE_TOOL = {
    "name": "save_student_profile",
    "description": (
        "Save the student's study profile. Call this once you have collected "
        "enough details to build a study plan: at minimum their goal, and "
        "ideally an exam date or timeframe, current level, weak topics and "
        "weekly study hours."
    ),
    "input_schema": {
        "type": "object",
        "properties": _PROFILE_PROPERTIES,
        "required": ["goal"],
    },
}

UPDATE_TOOL = {
    "name": "update_student_profile",
    "description": (
        "Update the student's saved study profile when they tell you something "
        "changed (new exam date, different weekly hours, new weak topics, a new "
        "goal). Only include the fields that changed. The study plan and its "
        "calendar sessions are then regenerated automatically."
    ),
    "input_schema": {"type": "object", "properties": _PROFILE_PROPERTIES},
}

INTERVIEW_TEMPLATE = """You are Briefly, a friendly study assistant helping a student set up a study space for "{name}".
Today's date is {today}.

Your job in this phase: have a short conversation to learn what you need to build a great study plan.
Collect: their goal (exam prep, learning the course, catching up), exam or deadline date, current level, topics they find hardest, and roughly how many hours per week they can study.

Rules:
- Ask at most 1-2 questions per message. Keep it conversational and encouraging.
- Never re-ask for things they already told you.
- If no source files are attached yet, you may mention they can upload materials or import them from Teams — but don't block on it.
- When you have enough information, call the save_student_profile tool (exam_date as YYYY-MM-DD), then tell the student you are generating their study plan, calendar sessions, notes, sample test and flashcards.
{sources_block}
"""

TUTOR_TEMPLATE = """You are Briefly, a study tutor for the subject "{name}".
Today's date is {today}.

Student profile:
{profile}

Use the course excerpts below as your primary reference (they were selected for the student's latest question). Answer questions, explain concepts, quiz the student, and point them to relevant parts of their study plan. If something isn't covered by the sources, say so and answer from general knowledge.

If the student says their situation changed (exam moved, fewer hours, new weak topics, a different goal), call update_student_profile with only the changed fields, then tell them their study plan is being rebuilt.
{sources_block}
"""

MAX_TOOL_LOOPS = 5
FALLBACK_REPLY = "I've got everything I need — working on your study materials now."


def text_of(blocks) -> str:
    return "".join(b.text for b in blocks if b.type == "text")


def _sources_block(space: SubjectSpace, preview_chars: int) -> str:
    if not space.sources:
        return "\nNo source files have been attached yet."
    lines = ["", "Attached sources:"]
    for s in space.sources:
        preview = (s.extracted_text or "")[:preview_chars].replace("\n", " ")
        lines.append(f"--- {s.filename} ---\n{preview}")
    return "\n".join(lines)


def _excerpts_block(space: SubjectSpace, query: str) -> str:
    if not space.sources:
        return "\nNo source files have been attached yet."
    excerpts = select_excerpts(space.sources, query, settings.tutor_context_chars)
    if not excerpts:
        names = ", ".join(s.filename for s in space.sources)
        return f"\nAttached sources (no readable text): {names}"
    lines = ["", "Course excerpts:"]
    lines += [f"--- {name} ---\n{chunk}" for name, chunk in excerpts]
    return "\n".join(lines)


def build_interview_system(space: SubjectSpace) -> str:
    return INTERVIEW_TEMPLATE.format(
        name=space.name,
        today=date.today().isoformat(),
        sources_block=_sources_block(space, 400),
    )


def _recent_user_text(history: list[dict], n: int = 2) -> str:
    texts = [m["content"] for m in history if m["role"] == "user" and isinstance(m["content"], str)]
    return " ".join(texts[-n:])


def build_tutor_system(space: SubjectSpace, history: list[dict] | None = None) -> str:
    profile = json.dumps(space.profile, indent=2) if space.profile else "(none)"
    query = _recent_user_text(history or [])
    return TUTOR_TEMPLATE.format(
        name=space.name,
        today=date.today().isoformat(),
        profile=profile,
        sources_block=_excerpts_block(space, query),
    )


def _serialize_blocks(blocks) -> list[dict]:
    out = []
    for b in blocks:
        if b.type == "text":
            out.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            out.append(
                {
                    "type": "tool_use",
                    "id": b.id,
                    "name": b.name,
                    "input": b.input,
                }
            )
    return out


def _run_loop(system, history, tools, on_tool, client=None) -> str | None:
    """Chat with tool use until the model answers in plain text.

    `on_tool(tool_use)` returns (result_text, is_error). Returns None if the
    model kept calling tools past MAX_TOOL_LOOPS.
    """
    messages = list(history)
    for _ in range(MAX_TOOL_LOOPS):
        resp = create_message(
            system=system, messages=messages, tools=tools, client=client
        )
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            return text_of(resp.content)

        messages.append(
            {"role": "assistant", "content": _serialize_blocks(resp.content)}
        )
        results = []
        for tu in tool_uses:
            content, is_error = on_tool(tu)
            result = {
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": content,
            }
            if is_error:
                result["is_error"] = True
            results.append(result)
        messages.append({"role": "user", "content": results})
    return None


def run_interview_turn(
    space: SubjectSpace, history: list[dict], client=None
) -> tuple[str, dict | None]:
    """Run one interview turn. Returns (reply_text, profile_or_None)."""
    profile: dict | None = None

    def on_tool(tu):
        nonlocal profile
        if tu.name == PROFILE_TOOL["name"]:
            profile = dict(tu.input)
            return "Profile saved. Study materials are being generated.", False
        return f"Unknown tool: {tu.name}", True

    reply = _run_loop(
        build_interview_system(space), history, [PROFILE_TOOL], on_tool, client
    )
    return (reply or FALLBACK_REPLY), profile


def run_tutor_turn(
    space: SubjectSpace, history: list[dict], client=None
) -> tuple[str, dict | None]:
    """Run one tutor turn. Returns (reply_text, profile_changes_or_None)."""
    changes: dict | None = None

    def on_tool(tu):
        nonlocal changes
        if tu.name == UPDATE_TOOL["name"]:
            changes = {**(changes or {}), **dict(tu.input)}
            return "Profile updated. The study plan is being rebuilt.", False
        return f"Unknown tool: {tu.name}", True

    reply = _run_loop(
        build_tutor_system(space, history), history, [UPDATE_TOOL], on_tool, client
    )
    return (reply or "Done — I've updated your study plan."), changes

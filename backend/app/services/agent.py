from ..models import SubjectSpace
from .llm import create_message

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
        "properties": {
            "goal": {
                "type": "string",
                "description": "What the student is working toward",
            },
            "exam_date": {
                "type": "string",
                "description": "Exam/deadline date, free text or ISO",
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
        },
        "required": ["goal"],
    },
}

INTERVIEW_TEMPLATE = """You are Briefly, a friendly study assistant helping a student set up a study space for "{name}".

Your job in this phase: have a short conversation to learn what you need to build a great study plan.
Collect: their goal (exam prep, learning the course, catching up), exam or deadline date, current level, topics they find hardest, and roughly how many hours per week they can study.

Rules:
- Ask at most 1-2 questions per message. Keep it conversational and encouraging.
- Never re-ask for things they already told you.
- If no source files are attached yet, you may mention they can upload materials or import them from Teams — but don't block on it.
- When you have enough information, call the save_student_profile tool, then tell the student you are generating their study plan, notes and a sample test.
{sources_block}
"""

TUTOR_TEMPLATE = """You are Briefly, a study tutor for the subject "{name}".

Student profile:
{profile}

Use the attached course sources as your primary reference. Answer questions, explain concepts, quiz the student, and point them to relevant parts of their study plan. If something isn't covered by the sources, say so and answer from general knowledge.
{sources_block}
"""

MAX_TOOL_LOOPS = 5


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


def build_interview_system(space: SubjectSpace) -> str:
    return INTERVIEW_TEMPLATE.format(
        name=space.name, sources_block=_sources_block(space, 400)
    )


def build_tutor_system(space: SubjectSpace) -> str:
    import json

    profile = json.dumps(space.profile, indent=2) if space.profile else "(none)"
    return TUTOR_TEMPLATE.format(
        name=space.name,
        profile=profile,
        sources_block=_sources_block(space, 4000),
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


def run_interview_turn(
    space: SubjectSpace, history: list[dict], client=None
) -> tuple[str, dict | None]:
    """Run one interview turn. Returns (reply_text, profile_or_None)."""
    messages = list(history)
    profile: dict | None = None
    for _ in range(MAX_TOOL_LOOPS):
        resp = create_message(
            system=build_interview_system(space),
            messages=messages,
            tools=[PROFILE_TOOL],
            client=client,
        )
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            return text_of(resp.content), profile

        messages.append(
            {"role": "assistant", "content": _serialize_blocks(resp.content)}
        )
        results = []
        for tu in tool_uses:
            if tu.name == "save_student_profile":
                profile = dict(tu.input)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": "Profile saved. Study materials are being generated.",
                    }
                )
            else:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": f"Unknown tool: {tu.name}",
                        "is_error": True,
                    }
                )
        messages.append({"role": "user", "content": results})

    return (
        "I've collected your details — generating your study materials now.",
        profile,
    )


def run_tutor_turn(space: SubjectSpace, history: list[dict], client=None) -> str:
    resp = create_message(
        system=build_tutor_system(space), messages=list(history), client=client
    )
    return text_of(resp.content)

"""AI enhancements for the student's own notes ("My notes" tab).

Each action is exactly one LLM call. Text actions return Markdown;
"flashcards" uses the generation.py pattern (forced tool call + validation +
one retry on malformed output) reusing its CARDS_TOOL and parse_cards.
"""

from ..models import SubjectSpace, UserNote
from .agent import text_of
from .generation import CARDS_TOOL, GenerationError, parse_cards
from .llm import RetryableLLMError, create_message, tool_input

ACTIONS = {
    "summarize": (
        "Summarise the note into a short bullet-point brief that keeps every "
        "key fact, formula and definition."
    ),
    "key_terms": (
        "Extract the key terms and concepts from the note as a Markdown "
        "glossary: '**term** — one-line definition', one per line."
    ),
    "simplify": (
        "Rewrite the note in simpler language for a beginner. Keep all "
        "important facts, use short sentences and add a brief analogy where "
        "it helps."
    ),
    "improve": (
        "Improve the note itself: tighten the wording, organise it under "
        "clear Markdown headings and bullets, fill obvious gaps and fix "
        "mistakes. Return only the improved note."
    ),
    "quiz_me": (
        "Write 4-6 self-quiz questions based only on the note. For each, give "
        "the question, then the answer on the next line as '> **Answer:** "
        "...'. Order them easy to hard."
    ),
    "flashcards": (
        "Turn the note into flashcards by calling submit_flashcards: one "
        "atomic fact, term or question per card (front), concise answer "
        "(back). Make 5-15 cards covering the whole note."
    ),
}


def _system(space: SubjectSpace) -> str:
    parts = [
        "You are a study assistant helping a student with their own notes "
        f'for the subject "{space.name}".'
    ]
    profile = space.profile or {}
    bits = [
        b
        for b in (
            f"level: {profile['level']}" if profile.get("level") else "",
            f"goal: {profile['goal']}" if profile.get("goal") else "",
        )
        if b
    ]
    if bits:
        parts.append("Student " + "; ".join(bits) + ".")
    parts.append(
        "Work only from the note below — do not invent unrelated content. "
        "Answer in Markdown."
    )
    return "\n".join(parts)


def _structured(system, context, tool, parser, client, max_tokens=4096):
    """Force a tool call, validate the result, retry once if unusable."""
    last_error = "the model did not return structured output"
    for _ in range(2):
        try:
            resp = create_message(
                system=system,
                messages=[{"role": "user", "content": context}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                max_tokens=max_tokens,
                client=client,
            )
        except RetryableLLMError as e:
            last_error = str(e)
            continue
        raw = tool_input(resp, tool["name"])
        if raw is None:
            continue
        try:
            return parser(raw)
        except GenerationError as e:
            last_error = str(e)
    raise GenerationError(last_error)


def enhance_note(
    space: SubjectSpace, note: UserNote, action: str, client=None
) -> dict:
    """Run one AI action on `note.content`. Never modifies the note itself.

    Returns {"result": <markdown>} or, for "flashcards",
    {"result": <markdown list>, "cards": [{"front", "back"}, ...]}.
    Raises GenerationError when the model's output is unusable.
    """
    if action not in ACTIONS:
        raise GenerationError(f"unknown action: {action}")
    context = (
        f'Student note "{note.title or "Untitled"}":\n\n{note.content}\n\n'
        + ACTIONS[action]
    )
    if action == "flashcards":
        data = _structured(
            _system(space), context, CARDS_TOOL, parse_cards, client
        )
        cards = data["cards"]
        result = "\n".join(f"- **{c['front']}** — {c['back']}" for c in cards)
        return {"result": result, "cards": cards}
    resp = create_message(
        system=_system(space),
        messages=[{"role": "user", "content": context}],
        client=client,
    )
    text = text_of(resp.content).strip()
    if not text:
        raise GenerationError("the AI returned an empty result")
    return {"result": text}

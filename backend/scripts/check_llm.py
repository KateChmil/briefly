"""Check that your AI key works, in about 10 seconds.

    cd backend
    python -m scripts.check_llm

Runs the same kinds of calls the app makes (plain text, a forced structured
output, a tool-calling round trip, and a real flashcard generation) against the
configured provider and prints PASS/FAIL for each. Your key is never printed.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.models import ArtifactKind  # noqa: E402
from app.services import agent, generation, llm  # noqa: E402

SAMPLE = (
    "Subject: Biology 101\n\n--- Source: cells.txt ---\n"
    "Mitochondria produce ATP through cellular respiration. Ribosomes build proteins "
    "from mRNA. The nucleus stores DNA. Prokaryotes have no nucleus."
)

ANSWER_TOOL = {
    "name": "report_answer",
    "description": "Report a yes/no answer.",
    "input_schema": {
        "type": "object",
        "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}},
        "required": ["answer"],
    },
}


def check_plain():
    resp = llm.create_message(
        system="Answer with one short word.",
        messages=[{"role": "user", "content": "Say pong."}],
        max_tokens=50,
    )
    text = agent.text_of(resp.content).strip()
    assert text, "the model returned no text"
    return f"replied {text[:40]!r}"


def check_forced_tool():
    resp = llm.create_message(
        system="Use the tool to answer.",
        messages=[{"role": "user", "content": "Is water wet?"}],
        tools=[ANSWER_TOOL],
        tool_choice={"type": "tool", "name": "report_answer"},
        max_tokens=100,
    )
    data = llm.tool_input(resp, "report_answer")
    assert data and data.get("answer") in ("yes", "no"), f"unexpected tool input: {data}"
    return f"structured output ok ({data['answer']})"


def check_tool_round_trip():
    seen = []

    def on_tool(tu):
        seen.append(tu.name)
        return "Profile saved.", False

    reply = agent._run_loop(
        "You are a study assistant. When the student states a goal, call "
        "save_student_profile, then confirm in one sentence.",
        [{"role": "user", "content": "My goal is to pass the biology final."}],
        [agent.PROFILE_TOOL],
        on_tool,
    )
    assert seen == ["save_student_profile"], f"tool was not called (calls: {seen})"
    return f"tool call + follow-up ok ({(reply or '(empty reply)')[:50]!r})"


def check_flashcards():
    gen = generation.generate_artifact(SAMPLE, ArtifactKind.flashcards)
    import json

    cards = json.loads(gen.content)["cards"]
    return f"generated {len(cards)} valid flashcards"


def main() -> int:
    provider = settings.provider
    key = settings.gemini_api_key if provider == "gemini" else settings.anthropic_api_key
    print(f"Provider: {provider}   Model: {settings.model_name}")
    if not key:
        print("FAIL  no API key found. Add GEMINI_API_KEY to backend/.env (see .env.example).")
        return 1
    print(f"Key:      set ({len(key)} characters)\n")

    failures = 0
    for name, fn in [
        ("plain text", check_plain),
        ("structured output", check_forced_tool),
        ("tool-calling round trip", check_tool_round_trip),
        ("flashcard generation", check_flashcards),
    ]:
        started = time.time()
        try:
            detail = fn()
            print(f"PASS  {name:<24} {detail}  [{time.time() - started:.1f}s]")
        except Exception as e:  # noqa: BLE001 - report everything
            failures += 1
            print(f"FAIL  {name:<24} {type(e).__name__}: {e}")
    print("\nAll good - the app will work." if not failures else f"\n{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

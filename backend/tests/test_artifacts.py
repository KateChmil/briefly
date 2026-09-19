from datetime import date, timedelta

import pytest

from app.services import generation
from app.services.generation import GenerationError
from tests.conftest import RouterClient, sample_tools


def test_regenerate_increments_version(client, monkeypatch):
    import app.services.llm as llm

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    fake = RouterClient(notes="notes v1")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    r1 = client.post(f"/api/spaces/{sid}/artifacts/notes/regenerate")
    assert r1.status_code == 200
    assert r1.json()["version"] == 1
    assert r1.json()["content"] == "notes v1"

    fake.notes = "notes v2"
    r2 = client.post(f"/api/spaces/{sid}/artifacts/notes/regenerate")
    assert r2.json()["version"] == 2
    assert r2.json()["content"] == "notes v2"

    # list returns only latest
    artifacts = client.get(f"/api/spaces/{sid}/artifacts").json()
    assert len(artifacts) == 1
    assert artifacts[0]["version"] == 2


def test_regenerate_reports_ai_failure(client, monkeypatch):
    import app.services.llm as llm

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    monkeypatch.setattr(llm, "get_client", lambda: RouterClient(notes=RuntimeError("nope")))
    r = client.post(f"/api/spaces/{sid}/artifacts/notes/regenerate")
    assert r.status_code == 502
    assert "nope" in r.json()["detail"]


def test_generate_requires_profile(client):
    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    assert client.post(f"/api/spaces/{sid}/generate").status_code == 400


def test_get_artifact_404(client):
    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    assert client.get(f"/api/spaces/{sid}/artifacts/notes").status_code == 404


# ---- validation of structured model output --------------------------------

TODAY = date(2026, 9, 19)


def d(n):
    return (TODAY + timedelta(days=n)).isoformat()


def test_parse_plan_drops_bad_and_out_of_range_sessions():
    raw = {
        "overview": "  go  ",
        "sessions": [
            {"date": d(3), "title": "Cells", "minutes": 45, "kind": "study"},
            {"date": d(-2), "title": "In the past", "minutes": 45, "kind": "study"},
            {"date": d(40), "title": "After the exam", "minutes": 45, "kind": "study"},
            {"date": "not-a-date", "title": "Broken", "minutes": 45, "kind": "study"},
            {"date": d(1), "title": "Odd kind", "minutes": 5000, "kind": "weird"},
        ],
    }
    plan = generation.parse_plan(raw, TODAY, exam=TODAY + timedelta(days=14))
    assert [s["title"] for s in plan["sessions"]] == ["Odd kind", "Cells"]
    assert plan["sessions"][0]["kind"] == "study"  # unknown kind coerced
    assert plan["sessions"][0]["minutes"] == 300  # clamped
    assert plan["overview"] == "go"


def test_parse_plan_without_usable_sessions_raises():
    with pytest.raises(GenerationError):
        generation.parse_plan({"overview": "x", "sessions": []}, TODAY, None)


def test_parse_quiz_repairs_and_filters():
    raw = {
        "title": "Quiz",
        "questions": [
            # answer differs in case/whitespace -> snapped to the real choice
            {"type": "mcq", "question": "Q1", "choices": ["Nucleus", "Mitochondria"], "answer": " mitochondria "},
            # answer given as a letter
            {"type": "mcq", "question": "Q2", "choices": ["A1", "B2", "C3"], "answer": "B"},
            {"type": "short", "question": "Q3", "answer": "DNA", "explanation": "e"},
            # invalid: answer not among choices / missing answer / not a dict
            {"type": "mcq", "question": "Q4", "choices": ["x", "y"], "answer": "z"},
            {"type": "short", "question": "Q5"},
            "garbage",
        ],
    }
    quiz = generation.parse_quiz(raw)
    assert [q["question"] for q in quiz["questions"]] == ["Q1", "Q2", "Q3"]
    assert quiz["questions"][0]["answer"] == "Mitochondria"
    assert quiz["questions"][1]["answer"] == "B2"
    assert all("explanation" in q for q in quiz["questions"])  # frontend can rely on it


def test_parse_quiz_too_few_questions_raises():
    with pytest.raises(GenerationError):
        generation.parse_quiz({"questions": [{"type": "short", "question": "Q", "answer": "A"}]})


def test_parse_cards():
    raw = {"cards": [{"front": f"f{i}", "back": f"b{i}"} for i in range(4)] + [{"front": "x"}]}
    assert len(generation.parse_cards(raw)["cards"]) == 4
    with pytest.raises(GenerationError):
        generation.parse_cards({"cards": [{"front": "a", "back": "b"}]})


def test_structured_output_is_retried_once():
    tools = sample_tools()
    tools["submit_sample_test"] = [{"title": "bad", "questions": []}, tools["submit_sample_test"]]
    fake = RouterClient(tools=tools)
    gen = generation.generate_artifact("ctx", generation.ArtifactKind.sample_test, client=fake)
    assert gen.format == "json"
    assert len(fake.calls) == 2


def test_structured_output_gives_up_after_retry():
    bad = {"title": "bad", "questions": []}
    fake = RouterClient(tools={"submit_sample_test": [bad, bad]})
    with pytest.raises(GenerationError):
        generation.generate_artifact("ctx", generation.ArtifactKind.sample_test, client=fake)
    assert len(fake.calls) == 2


def test_generation_calls_force_the_tool():
    fake = RouterClient(tools=sample_tools())
    generation.generate_artifact("ctx", generation.ArtifactKind.flashcards, client=fake)
    call = fake.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "submit_flashcards"}

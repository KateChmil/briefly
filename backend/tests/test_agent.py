import json
from datetime import date, timedelta
from types import SimpleNamespace

from app.services import agent
from tests.conftest import (
    FakeClient,
    FakeResponse,
    RouterClient,
    sample_tools,
    text_block,
    tool_use_block,
)


def make_space(name="Biology", sources=None, profile=None):
    return SimpleNamespace(name=name, sources=sources or [], profile=profile)


def test_interview_plain_reply():
    client = FakeClient(
        [FakeResponse([text_block("When is your exam?")])]
    )
    reply, profile = agent.run_interview_turn(
        make_space(), [{"role": "user", "content": "Hi"}], client=client
    )
    assert reply == "When is your exam?"
    assert profile is None


def test_interview_tool_use_loop():
    tool_resp = FakeResponse(
        [
            text_block("Thanks!"),
            tool_use_block(
                "save_student_profile",
                {"goal": "pass final", "exam_date": "2026-10-01"},
            ),
        ],
        stop_reason="tool_use",
    )
    final = FakeResponse([text_block("Generating your materials now!")])
    client = FakeClient([tool_resp, final])

    reply, profile = agent.run_interview_turn(
        make_space(), [{"role": "user", "content": "Final Oct 1"}], client=client
    )
    assert profile == {"goal": "pass final", "exam_date": "2026-10-01"}
    assert reply == "Generating your materials now!"

    # second call should contain the tool_result
    second_call = client.messages.calls[1]
    assert second_call["messages"][-1]["role"] == "user"
    assert second_call["messages"][-1]["content"][0]["type"] == "tool_result"


def test_interview_falls_back_when_model_loops_on_tools():
    looping = [
        FakeResponse(
            [tool_use_block("save_student_profile", {"goal": "x"}, id_=f"t{i}")],
            stop_reason="tool_use",
        )
        for i in range(agent.MAX_TOOL_LOOPS)
    ]
    reply, profile = agent.run_interview_turn(
        make_space(), [{"role": "user", "content": "hi"}], client=FakeClient(looping)
    )
    assert reply == agent.FALLBACK_REPLY
    assert profile == {"goal": "x"}


def test_tutor_turn_uses_relevant_excerpts():
    filler = "\n\n".join(f"Filler paragraph number {i} about nothing." for i in range(200))
    src = SimpleNamespace(
        filename="cells.txt",
        extracted_text=filler + "\n\nMitochondria produce ATP through respiration.",
    )
    client = FakeClient([FakeResponse([text_block("answer")])])
    reply, changes = agent.run_tutor_turn(
        make_space(sources=[src]),
        [{"role": "user", "content": "what makes ATP?"}],
        client=client,
    )
    assert reply == "answer"
    assert changes is None
    system = client.messages.calls[0]["system"]
    # the relevant paragraph sits far beyond the old 4000-char preview
    assert "Mitochondria produce ATP" in system
    assert "cells.txt" in system


def test_tutor_can_update_profile():
    tool_resp = FakeResponse(
        [tool_use_block("update_student_profile", {"weekly_hours": 4})],
        stop_reason="tool_use",
    )
    client = FakeClient([tool_resp, FakeResponse([text_block("Plan rebuilt!")])])
    reply, changes = agent.run_tutor_turn(
        make_space(profile={"goal": "pass"}),
        [{"role": "user", "content": "I only have 4 hours a week now"}],
        client=client,
    )
    assert changes == {"weekly_hours": 4}
    assert reply == "Plan rebuilt!"


def interview_chat(*texts_then_tool):
    """Chat script: a plain question, then the profile tool call, then a closing line."""
    return [
        FakeResponse([text_block("When is the exam?")]),
        FakeResponse(
            [tool_use_block("save_student_profile", texts_then_tool[0])],
            stop_reason="tool_use",
        ),
        FakeResponse([text_block("Generating now!")]),
    ]


def test_chat_endpoint_interview_flow(client, monkeypatch):
    import app.services.llm as llm

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    exam = (date.today() + timedelta(days=10)).isoformat()
    fake = RouterClient(
        tools=sample_tools(),
        chat=interview_chat({"goal": "pass", "exam_date": exam, "weekly_hours": 6}),
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    r1 = client.post(f"/api/spaces/{sid}/chat", json={"content": "hi"})
    assert r1.json()["message"]["content"] == "When is the exam?"
    assert r1.json()["profile_completed"] is False

    r2 = client.post(f"/api/spaces/{sid}/chat", json={"content": "exam soon, want to pass"})
    body = r2.json()
    assert body["profile_completed"] is True
    assert body["space_status"] == "generating"

    # The background job has finished by the time the test client returns.
    detail = client.get(f"/api/spaces/{sid}").json()
    assert detail["status"] == "ready"
    assert detail["exam_date"] == exam

    artifacts = {a["kind"]: a for a in client.get(f"/api/spaces/{sid}/artifacts").json()}
    assert set(artifacts) == {"study_plan", "notes", "sample_test", "flashcards"}
    quiz = json.loads(artifacts["sample_test"]["content"])
    assert quiz["questions"][0]["answer"] == "Mitochondria"
    plan = json.loads(artifacts["study_plan"]["content"])
    assert len(plan["sessions"]) == 3

    sessions = client.get(f"/api/spaces/{sid}/sessions").json()
    assert len(sessions) == 3 and not any(s["done"] for s in sessions)


def test_failed_generation_does_not_leave_space_ready(client, monkeypatch):
    """Regression: a failed job used to mark the space 'ready' with no artifacts."""
    import app.services.llm as llm

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    boom = RuntimeError("model overloaded")
    fake = RouterClient(
        tools={
            "submit_study_plan": boom,
            "submit_sample_test": boom,
            "submit_flashcards": boom,
        },
        chat=interview_chat({"goal": "pass"})[1:],
        notes=boom,
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    r = client.post(f"/api/spaces/{sid}/chat", json={"content": "I want to pass"})
    assert r.status_code == 200

    detail = client.get(f"/api/spaces/{sid}").json()
    assert detail["status"] == "interviewing"  # not 'ready'
    assert detail["profile"] == {"goal": "pass"}  # kept, so the retry needs no re-interview
    assert client.get(f"/api/spaces/{sid}/artifacts").json() == []

    msgs = client.get(f"/api/spaces/{sid}/messages").json()
    assert "couldn't finish" in msgs[-1]["content"]

    # Retry from the saved profile succeeds once the model recovers.
    monkeypatch.setattr(llm, "get_client", lambda: RouterClient(tools=sample_tools()))
    assert client.post(f"/api/spaces/{sid}/generate").status_code == 202
    assert client.get(f"/api/spaces/{sid}").json()["status"] == "ready"
    assert len(client.get(f"/api/spaces/{sid}/artifacts").json()) == 4


def test_partial_failure_keeps_successful_artifacts(client, monkeypatch):
    import app.services.llm as llm

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    tools = sample_tools()
    tools["submit_flashcards"] = RuntimeError("boom")
    fake = RouterClient(tools=tools, chat=interview_chat({"goal": "pass"})[1:])
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    client.post(f"/api/spaces/{sid}/chat", json={"content": "go"})
    assert client.get(f"/api/spaces/{sid}").json()["status"] == "ready"
    kinds = {a["kind"] for a in client.get(f"/api/spaces/{sid}/artifacts").json()}
    assert kinds == {"study_plan", "notes", "sample_test"}


def test_ai_error_in_chat_drops_unanswered_message(client, monkeypatch):
    import app.services.llm as llm

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]

    class Broken:
        class messages:
            @staticmethod
            def create(**_kw):
                raise ConnectionError("network down")

    monkeypatch.setattr(llm, "get_client", lambda: Broken)
    r = client.post(f"/api/spaces/{sid}/chat", json={"content": "hello"})
    assert r.status_code == 502
    msgs = client.get(f"/api/spaces/{sid}/messages").json()
    assert [m["role"] for m in msgs] == ["assistant"]  # only the greeting remains


def test_tutor_profile_update_rebuilds_plan(client, monkeypatch):
    import app.services.llm as llm

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    fake = RouterClient(tools=sample_tools(), chat=interview_chat({"goal": "pass"})[1:])
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    client.post(f"/api/spaces/{sid}/chat", json={"content": "go"})
    assert client.get(f"/api/spaces/{sid}").json()["status"] == "ready"

    # tick one session, then change hours via the tutor: the plan is rebuilt
    first = client.get(f"/api/spaces/{sid}/sessions").json()[0]
    client.patch(f"/api/sessions/{first['id']}", json={"done": True})

    fake.chat = [
        FakeResponse(
            [tool_use_block("update_student_profile", {"weekly_hours": 3})],
            stop_reason="tool_use",
        ),
        FakeResponse([text_block("Rebuilding your plan.")]),
    ]
    r = client.post(f"/api/spaces/{sid}/chat", json={"content": "only 3 hours a week now"})
    assert r.json()["plan_updating"] is True
    detail = client.get(f"/api/spaces/{sid}").json()
    assert detail["status"] == "ready"
    assert detail["profile"]["weekly_hours"] == 3
    plan = client.get(f"/api/spaces/{sid}/artifacts/study_plan").json()
    assert plan["version"] == 2
    sessions = client.get(f"/api/spaces/{sid}/sessions").json()
    assert any(s["done"] for s in sessions)  # ticks survive an identical session

import json
from types import SimpleNamespace

from app.services import agent
from tests.conftest import FakeClient, FakeResponse, text_block, tool_use_block


def make_space(name="Biology", sources=None):
    return SimpleNamespace(name=name, sources=sources or [], profile=None)


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


def test_tutor_turn_includes_sources():
    src = SimpleNamespace(
        filename="cells.txt", extracted_text="Mitochondria produce ATP"
    )
    client = FakeClient([FakeResponse([text_block("answer")])])
    reply = agent.run_tutor_turn(
        make_space(sources=[src]),
        [{"role": "user", "content": "what makes ATP?"}],
        client=client,
    )
    assert reply == "answer"
    system = client.messages.calls[0]["system"]
    assert "Mitochondria produce ATP" in system
    assert "cells.txt" in system


def test_chat_endpoint_interview_flow(client, monkeypatch):
    import app.services.llm as llm

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]

    # 1st user msg -> plain question; 2nd -> tool_use then final text;
    # then 3 generation calls
    fake = FakeClient(
        [
            FakeResponse([text_block("When is the exam?")]),
            FakeResponse(
                [tool_use_block("save_student_profile", {"goal": "pass"})],
                stop_reason="tool_use",
            ),
            FakeResponse([text_block("Generating now!")]),
            FakeResponse([text_block("# Plan\nWeek 1: cells")]),
            FakeResponse([text_block("# Notes\nCells...")]),
            FakeResponse(
                [
                    text_block(
                        json.dumps(
                            {
                                "title": "Bio quiz",
                                "questions": [
                                    {
                                        "type": "mcq",
                                        "question": "ATP organelle?",
                                        "choices": ["Nucleus", "Mitochondria"],
                                        "answer": "Mitochondria",
                                        "explanation": "site of respiration",
                                    }
                                ],
                            }
                        )
                    )
                ]
            ),
        ]
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    r1 = client.post(f"/api/spaces/{sid}/chat", json={"content": "hi"})
    assert r1.json()["message"]["content"] == "When is the exam?"
    assert r1.json()["profile_completed"] is False

    r2 = client.post(
        f"/api/spaces/{sid}/chat", json={"content": "exam oct 1, want to pass"}
    )
    body = r2.json()
    assert body["profile_completed"] is True
    assert body["space_status"] == "ready"

    artifacts = client.get(f"/api/spaces/{sid}/artifacts").json()
    kinds = {a["kind"]: a for a in artifacts}
    assert set(kinds) == {"study_plan", "notes", "sample_test"}
    assert kinds["sample_test"]["format"] == "json"
    quiz = json.loads(kinds["sample_test"]["content"])
    assert quiz["questions"][0]["answer"] == "Mitochondria"

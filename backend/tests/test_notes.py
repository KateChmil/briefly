import types

import pytest

import app.services.llm as llm
from app.services import notes_ai
from app.services.generation import GenerationError
from tests.conftest import RouterClient, sample_tools


def _space(client, name="Bio"):
    return client.post("/api/spaces", json={"name": name}).json()["id"]


def _note(client, space_id, title="Ch 1", content="Cells have nuclei."):
    r = client.post(
        f"/api/spaces/{space_id}/notes",
        json={"title": title, "content": content},
    )
    assert r.status_code == 201
    return r.json()


# ---- CRUD -----------------------------------------------------------------


def test_note_crud_and_persistence(client):
    sid = _space(client)
    note = _note(client, sid)
    assert note["title"] == "Ch 1"
    assert note["content"] == "Cells have nuclei."
    assert note["space_id"] == sid

    notes = client.get(f"/api/spaces/{sid}/notes").json()
    assert [n["id"] for n in notes] == [note["id"]]

    r = client.patch(f"/api/notes/{note['id']}", json={"content": "Updated body"})
    assert r.status_code == 200
    assert r.json()["content"] == "Updated body"
    assert r.json()["title"] == "Ch 1"  # untouched field kept
    assert (
        client.get(f"/api/spaces/{sid}/notes").json()[0]["content"]
        == "Updated body"
    )

    assert client.delete(f"/api/notes/{note['id']}").status_code == 204
    assert client.get(f"/api/spaces/{sid}/notes").json() == []


def test_notes_are_deleted_with_the_space(client):
    sid = _space(client)
    note = _note(client, sid)
    assert client.delete(f"/api/spaces/{sid}").status_code == 204
    assert (
        client.patch(
            f"/api/notes/{note['id']}", json={"title": "x"}
        ).status_code
        == 404
    )


def test_note_content_limit(client):
    sid = _space(client)
    r = client.post(
        f"/api/spaces/{sid}/notes",
        json={"title": "big", "content": "x" * 20_001},
    )
    assert r.status_code == 422


def test_note_endpoints_404(client):
    assert (
        client.patch("/api/notes/999", json={"title": "x"}).status_code == 404
    )
    assert client.delete("/api/notes/999").status_code == 404
    assert (
        client.post(
            "/api/notes/999/enhance", json={"action": "summarize"}
        ).status_code
        == 404
    )
    assert client.get("/api/spaces/nope/notes").status_code == 404


# ---- enhance ---------------------------------------------------------------


def test_enhance_text_action(client, monkeypatch):
    sid = _space(client)
    note = _note(client, sid)
    fake = RouterClient(notes="- short summary")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    r = client.post(
        f"/api/notes/{note['id']}/enhance", json={"action": "summarize"}
    )
    assert r.status_code == 200
    assert r.json() == {"result": "- short summary", "cards": None}
    assert len(fake.calls) == 1
    assert not fake.calls[0].get("tools")  # plain call, no forced tool

    # the note itself is untouched
    assert (
        client.get(f"/api/spaces/{sid}/notes").json()[0]["content"]
        == "Cells have nuclei."
    )


def test_enhance_all_text_actions(client, monkeypatch):
    sid = _space(client)
    note = _note(client, sid)
    fake = RouterClient(notes="ok")
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    for action in ("summarize", "key_terms", "simplify", "improve", "quiz_me"):
        r = client.post(
            f"/api/notes/{note['id']}/enhance", json={"action": action}
        )
        assert r.status_code == 200, action
        assert r.json()["result"] == "ok"
    assert len(fake.calls) == 5  # exactly one call per request


def test_enhance_flashcards_returns_cards(client, monkeypatch):
    sid = _space(client)
    note = _note(client, sid)
    fake = RouterClient(tools=sample_tools())
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    r = client.post(
        f"/api/notes/{note['id']}/enhance", json={"action": "flashcards"}
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 5
    assert {"front": "Term 0", "back": "Definition 0"} in body["cards"]
    assert "Term 0" in body["result"]  # markdown list mirrors the cards
    assert fake.calls[0]["tool_choice"] == {
        "type": "tool",
        "name": "submit_flashcards",
    }


def test_enhance_bad_ai_output_is_a_clean_error(client, monkeypatch):
    sid = _space(client)
    note = _note(client, sid)
    fake = RouterClient(
        tools={"submit_flashcards": [{"cards": []}, {"cards": []}]}
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    r = client.post(
        f"/api/notes/{note['id']}/enhance", json={"action": "flashcards"}
    )
    assert r.status_code == 502
    assert "flashcards" in r.json()["detail"]
    assert len(fake.calls) == 2  # retried once, then gave up cleanly


def test_enhance_ai_failure_is_friendly(client, monkeypatch):
    sid = _space(client)
    note = _note(client, sid)
    monkeypatch.setattr(
        llm,
        "get_client",
        lambda: RouterClient(notes=RuntimeError("rate limited")),
    )
    r = client.post(
        f"/api/notes/{note['id']}/enhance", json={"action": "summarize"}
    )
    assert r.status_code == 502
    assert "rate limited" in r.json()["detail"]


def test_enhance_unknown_action_422(client):
    sid = _space(client)
    note = _note(client, sid)
    r = client.post(
        f"/api/notes/{note['id']}/enhance", json={"action": "dance"}
    )
    assert r.status_code == 422


def test_enhance_empty_note_400(client):
    sid = _space(client)
    note = _note(client, sid, content="   ")
    r = client.post(
        f"/api/notes/{note['id']}/enhance", json={"action": "summarize"}
    )
    assert r.status_code == 400
    assert "empty" in r.json()["detail"].lower()


def test_enhance_note_service_directly():
    space = types.SimpleNamespace(name="Bio", profile={"level": "beginner"})
    note = types.SimpleNamespace(title="T", content="Some text")
    out = notes_ai.enhance_note(
        space, note, "improve", client=RouterClient(notes="better")
    )
    assert out == {"result": "better"}
    with pytest.raises(GenerationError):
        notes_ai.enhance_note(
            space, note, "improve", client=RouterClient(notes="")
        )

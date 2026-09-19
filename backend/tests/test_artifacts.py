import json

from app.services import generation
from tests.conftest import FakeClient, FakeResponse, text_block


def test_regenerate_increments_version(client, monkeypatch):
    import app.services.llm as llm

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    fake = FakeClient(
        [
            FakeResponse([text_block("plan v1")]),
            FakeResponse([text_block("plan v2")]),
        ]
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    r1 = client.post(f"/api/spaces/{sid}/artifacts/study_plan/regenerate")
    assert r1.status_code == 200
    assert r1.json()["version"] == 1
    assert r1.json()["content"] == "plan v1"

    r2 = client.post(f"/api/spaces/{sid}/artifacts/study_plan/regenerate")
    assert r2.json()["version"] == 2
    assert r2.json()["content"] == "plan v2"

    # list returns only latest
    artifacts = client.get(f"/api/spaces/{sid}/artifacts").json()
    assert len(artifacts) == 1
    assert artifacts[0]["version"] == 2


def test_get_artifact_404(client):
    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    assert client.get(f"/api/spaces/{sid}/artifacts/notes").status_code == 404


def test_parse_json_handles_fences():
    text = '```json\n{"a": 1}\n```'
    assert json.loads(generation._parse_json(text)) == {"a": 1}


def test_parse_json_handles_surrounding_text():
    text = 'Here you go: {"b": 2} done'
    assert json.loads(generation._parse_json(text)) == {"b": 2}


def test_parse_json_invalid():
    assert generation._parse_json("no json here") is None

import pytest


@pytest.fixture
def teams_fixture(mock_teams_dir):
    (mock_teams_dir / "History" / "Lectures").mkdir(parents=True, exist_ok=True)
    (mock_teams_dir / "History" / "Lectures" / "ww2.txt").write_text(
        "WW2 lecture notes"
    )
    (mock_teams_dir / "History" / "Readings").mkdir(
        parents=True, exist_ok=True
    )
    return mock_teams_dir


def test_browse_teams(client, teams_fixture):
    teams = client.get("/api/teams").json()
    assert teams == [{"id": "History", "name": "History"}]

    channels = client.get("/api/teams/channels", params={"team_id": "History"}).json()
    names = {c["name"] for c in channels}
    assert names == {"Lectures", "Readings"}

    files = client.get(
        "/api/teams/files", params={"channel_id": "History/Lectures"}
    ).json()
    assert files[0]["name"] == "ww2.txt"


def test_import_from_teams(client, teams_fixture):
    sid = client.post("/api/spaces", json={"name": "History"}).json()["id"]
    r = client.post(
        f"/api/spaces/{sid}/sources/teams",
        json={"file_ids": ["History/Lectures/ww2.txt", "bad/id.txt"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["imported"]) == 1
    assert data["imported"][0]["origin"] == "teams"
    assert data["imported"][0]["teams_ref"]["file_id"] == "History/Lectures/ww2.txt"
    assert len(data["skipped"]) == 1


def test_traversal_rejected(client, teams_fixture):
    r = client.get("/api/teams/channels", params={"team_id": "../../etc"})
    assert r.status_code == 400

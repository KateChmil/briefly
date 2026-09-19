def test_create_space(client):
    r = client.post("/api/spaces", json={"name": "Biology"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Biology"
    assert data["status"] == "interviewing"
    assert data["sources"] == []

    msgs = client.get(f"/api/spaces/{data['id']}/messages").json()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "assistant"


def test_list_and_get_space(client):
    sid = client.post("/api/spaces", json={"name": "Calc"}).json()["id"]
    spaces = client.get("/api/spaces").json()
    assert any(s["id"] == sid for s in spaces)
    detail = client.get(f"/api/spaces/{sid}").json()
    assert detail["name"] == "Calc"


def test_delete_space(client):
    sid = client.post("/api/spaces", json={"name": "Temp"}).json()["id"]
    assert client.delete(f"/api/spaces/{sid}").status_code == 204
    assert client.get(f"/api/spaces/{sid}").status_code == 404


def test_get_missing_space(client):
    assert client.get("/api/spaces/nope").status_code == 404


def test_create_space_blank_name(client):
    assert client.post("/api/spaces", json={"name": "  "}).status_code == 422

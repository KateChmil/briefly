import json
import urllib.error

import pytest


@pytest.fixture
def canvas_fixture(mock_canvas_dir):
    course = mock_canvas_dir / "Biology 101"
    (course / "files").mkdir(parents=True, exist_ok=True)
    (course / "files" / "cells.txt").write_text("Cell structure notes")
    (course / "files" / "genetics.txt").write_text("Genetics notes")
    (course / "assignments.json").write_text(
        json.dumps(
            [
                {
                    "id": "a1",
                    "name": "Reading: cells",
                    "due_at": "2030-01-10T23:59:00",
                    "description": "",
                },
                {
                    "id": "a2",
                    "name": "Midterm quiz",
                    "due_at": "2030-01-15T10:00:00",
                    "description": "Chapters 1-4",
                },
                {"id": "a3", "name": "No date homework", "due_at": None},
            ]
        )
    )
    (mock_canvas_dir / "Calculus II" / "files").mkdir(parents=True, exist_ok=True)
    (mock_canvas_dir / "Calculus II" / "assignments.json").write_text("[]")
    return mock_canvas_dir


def test_status_is_mock(client, canvas_fixture):
    assert client.get("/api/canvas/status").json() == {"mode": "mock"}


def test_list_courses_files_assignments(client, canvas_fixture):
    courses = client.get("/api/canvas/courses").json()
    assert [c["name"] for c in courses] == ["Biology 101", "Calculus II"]

    files = client.get("/api/canvas/courses/Biology%20101/files").json()
    assert {f["name"] for f in files} == {"cells.txt", "genetics.txt"}

    assignments = client.get("/api/canvas/courses/Biology%20101/assignments").json()
    assert len(assignments) == 3
    assert assignments[0]["due_at"].startswith("2030-01-10")


def test_import_files(client, canvas_fixture):
    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    r = client.post(
        f"/api/spaces/{sid}/sources/canvas",
        json={
            "file_ids": [
                "Biology 101/files/cells.txt",
                "Biology 101/files/missing.txt",
                "../secret.txt",
            ]
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["imported"]) == 1
    assert data["imported"][0]["origin"] == "canvas"
    assert data["imported"][0]["filename"] == "cells.txt"
    assert len(data["skipped"]) == 2


def test_import_due_dates_dedupes(client, canvas_fixture):
    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    url = f"/api/spaces/{sid}/calendar/canvas-assignments"
    r = client.post(url, json={"course_id": "Biology 101"})
    assert r.status_code == 200
    assert r.json() == {"imported": 2, "skipped": 1}

    r2 = client.post(url, json={"course_id": "Biology 101"})
    assert r2.json() == {"imported": 0, "skipped": 3}

    items = client.get(
        "/api/calendar",
        params={"space_id": sid, "start": "2030-01-01", "end": "2030-02-01"},
    ).json()
    by_title = {i["title"]: i for i in items}
    assert by_title["Reading: cells"]["kind"] == "other"
    assert by_title["Reading: cells"]["start_time"] is None  # 23:59 -> all-day
    assert by_title["Midterm quiz"]["kind"] == "exam"
    assert by_title["Midterm quiz"]["start_time"] == "10:00"


def test_mock_provider_rejects_bad_ids(canvas_fixture):
    from app.services.canvas_provider import MockCanvasProvider

    p = MockCanvasProvider(canvas_fixture)
    for bad in ("..", "../..", "../../etc"):
        with pytest.raises(ValueError):
            p.list_files(bad)
        with pytest.raises(ValueError):
            p.list_assignments(bad)
        with pytest.raises(ValueError):
            p.read_file(bad + "/x.txt")
    with pytest.raises(FileNotFoundError):
        p.read_file("Biology 101/files/nope.txt")


def test_http_provider_with_fake_transport():
    from app.services.canvas_provider import HttpCanvasProvider

    calls = []
    base = "https://canvas.test"

    def transport(req):
        calls.append(req)
        u = req.full_url
        if u == f"{base}/api/v1/courses?per_page=100&enrollment_state=active":
            return json.dumps([{"id": 5, "name": "Bio"}]).encode()
        if u == f"{base}/api/v1/courses/5/assignments?per_page=100":
            return json.dumps(
                [{"id": 7, "name": "Quiz 1", "due_at": "2030-05-01T09:00:00Z"}]
            ).encode()
        if u == f"{base}/api/v1/courses/5/files?per_page=100":
            return json.dumps([{"id": 9, "display_name": "notes.txt"}]).encode()
        if u == f"{base}/api/v1/files/9":
            return json.dumps(
                {
                    "id": 9,
                    "display_name": "notes.txt",
                    "url": "https://cdn.test/dl/9",
                }
            ).encode()
        if u == "https://cdn.test/dl/9":
            return b"file bytes"
        raise AssertionError(f"unexpected URL {u}")

    p = HttpCanvasProvider(base, "secret-token", transport=transport)
    assert [c.name for c in p.list_courses()] == ["Bio"]
    a = p.list_assignments("5")[0]
    assert a.name == "Quiz 1" and a.due_at is not None and a.due_at.year == 2030
    assert [f.name for f in p.list_files("5")] == ["notes.txt"]
    assert p.read_file("9") == ("notes.txt", b"file bytes")

    # Bearer token goes to the Canvas API only, never to the download CDN.
    assert calls[0].get_header("Authorization") == "Bearer secret-token"
    assert calls[-1].get_header("Authorization") is None
    # The token never appears in exceptions or returned data.
    with pytest.raises(ValueError):
        p.read_file("../evil")
    assert len(calls) == 5  # the bad id never hit the "network"


def test_http_provider_rejects_http_and_surfaces_errors():
    from app.services.canvas_provider import CanvasError, HttpCanvasProvider

    with pytest.raises(ValueError):
        HttpCanvasProvider("http://canvas.test", "t")

    def failing(req):
        raise urllib.error.URLError("down")

    p = HttpCanvasProvider("https://canvas.test", "t", transport=failing)
    with pytest.raises(CanvasError, match="Could not reach Canvas"):
        p.list_courses()

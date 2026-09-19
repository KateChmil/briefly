"""Canvas LMS provider: mock fixtures now, real Canvas REST API when configured.

CanvasProvider is a Protocol so the router never cares which implementation it
gets. MockCanvasProvider reads backend/app/mock_canvas/<course>/; the layout is
a course directory holding assignments.json and a files/ subfolder:

    mock_canvas/
      Biology 101/
        assignments.json   # [{"id", "name", "due_at"|"due_in_days", ...}]
        files/
          cell-structure.txt
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import quote, urlparse

MAX_FILE_BYTES = 10 * 1024 * 1024
ALL_DAY_DUE = time(23, 59)  # Canvas' default due time; shown as all-day


@dataclass
class CanvasCourse:
    id: str
    name: str


@dataclass
class CanvasAssignment:
    id: str
    name: str
    due_at: datetime | None
    description: str = ""


@dataclass
class CanvasFile:
    id: str
    name: str


class CanvasProvider(Protocol):
    """Interface for a Canvas data source. IDs are opaque strings to callers."""

    def list_courses(self) -> list[CanvasCourse]: ...
    def list_assignments(self, course_id: str) -> list[CanvasAssignment]: ...
    def list_files(self, course_id: str) -> list[CanvasFile]: ...
    def read_file(self, file_id: str) -> tuple[str, bytes]: ...


def parse_due(value) -> datetime | None:
    """Parse a Canvas ISO 8601 `due_at` into a naive local datetime."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


class MockCanvasProvider:
    """Directory-backed fake Canvas: root/<course>/{assignments.json, files/}.

    IDs are POSIX relative paths: the course id is the directory name and a
    file id is "<course>/files/<name>" (same convention as MockTeamsProvider).
    Besides an ISO "due_at", fixtures may use "due_in_days" (+ optional
    "due_time") so demo deadlines always land in the near future.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    def _resolve(self, rel_id: str) -> Path:
        p = (self.root / rel_id).resolve()
        if self.root != p and self.root not in p.parents:
            raise ValueError(f"Invalid id: {rel_id}")
        return p

    def list_courses(self) -> list[CanvasCourse]:
        if not self.root.is_dir():
            return []
        return [
            CanvasCourse(id=d.name, name=d.name)
            for d in sorted(self.root.iterdir())
            if d.is_dir()
        ]

    def list_assignments(self, course_id: str) -> list[CanvasAssignment]:
        path = self._resolve(course_id) / "assignments.json"
        if not path.is_file():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            out.append(
                CanvasAssignment(
                    id=str(item.get("id") or name),
                    name=name,
                    due_at=self._due(item),
                    description=str(item.get("description") or ""),
                )
            )
        return out

    @staticmethod
    def _due(item: dict) -> datetime | None:
        if isinstance(item.get("due_in_days"), int):
            try:
                t = datetime.strptime(str(item.get("due_time") or ""), "%H:%M").time()
            except ValueError:
                t = ALL_DAY_DUE
            return datetime.combine(
                date.today() + timedelta(days=item["due_in_days"]), t
            )
        return parse_due(item.get("due_at"))

    def list_files(self, course_id: str) -> list[CanvasFile]:
        files_dir = self._resolve(course_id) / "files"
        if not files_dir.is_dir():
            return []
        return [
            CanvasFile(id=f"{course_id}/files/{f.name}", name=f.name)
            for f in sorted(files_dir.iterdir())
            if f.is_file()
        ]

    def read_file(self, file_id: str) -> tuple[str, bytes]:
        p = self._resolve(file_id)
        if not p.is_file():
            raise FileNotFoundError(file_id)
        return p.name, p.read_bytes()


class CanvasError(RuntimeError):
    """The Canvas API was unreachable or rejected the request.

    Messages never contain the token.
    """


Transport = Callable[[urllib.request.Request], bytes]


def _default_transport(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=15) as r:  # noqa: S310
        return r.read(MAX_FILE_BYTES + 1)


class HttpCanvasProvider:
    """Canvas REST API (api/v1) provider using a bearer token.

    `transport` takes a urllib Request and returns the response body as bytes;
    it is injectable so tests never touch the network. The bearer token is only
    sent to URLs under `base_url` — file downloads use Canvas' pre-signed `url`
    without the Authorization header so the token cannot leak to a CDN host.
    """

    def __init__(
        self, base_url: str, token: str, transport: Transport | None = None
    ):
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("CANVAS_BASE_URL must be an https:// URL")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._transport = transport or _default_transport

    def _get_json(self, path: str):
        req = urllib.request.Request(
            f"{self.base_url}/api/v1{path}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
        )
        try:
            data = self._transport(req)
        except urllib.error.HTTPError as e:
            raise CanvasError(f"Canvas returned HTTP {e.code}.") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise CanvasError("Could not reach Canvas.") from e
        try:
            return json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise CanvasError("Canvas returned an unexpected response.") from e

    @staticmethod
    def _path_id(raw: str) -> str:
        value = str(raw).strip()
        if not value:
            raise ValueError("Invalid id: empty")
        return quote(value, safe="")

    def list_courses(self) -> list[CanvasCourse]:
        data = self._get_json("/courses?per_page=100&enrollment_state=active")
        out = []
        for c in data if isinstance(data, list) else []:
            if isinstance(c, dict) and "id" in c:
                out.append(
                    CanvasCourse(
                        id=str(c["id"]),
                        name=str(c.get("name") or f"Course {c['id']}"),
                    )
                )
        return out

    def list_assignments(self, course_id: str) -> list[CanvasAssignment]:
        data = self._get_json(
            f"/courses/{self._path_id(course_id)}/assignments?per_page=100"
        )
        out = []
        for a in data if isinstance(data, list) else []:
            if not isinstance(a, dict):
                continue
            name = str(a.get("name") or "").strip()
            if not name:
                continue
            out.append(
                CanvasAssignment(
                    id=str(a.get("id") or name),
                    name=name,
                    due_at=parse_due(a.get("due_at")),
                    description=str(a.get("description") or ""),
                )
            )
        return out

    def list_files(self, course_id: str) -> list[CanvasFile]:
        data = self._get_json(
            f"/courses/{self._path_id(course_id)}/files?per_page=100"
        )
        out = []
        for f in data if isinstance(data, list) else []:
            if isinstance(f, dict) and "id" in f:
                out.append(
                    CanvasFile(
                        id=str(f["id"]),
                        name=str(
                            f.get("display_name")
                            or f.get("filename")
                            or f"canvas-file-{f['id']}"
                        ),
                    )
                )
        return out

    def read_file(self, file_id: str) -> tuple[str, bytes]:
        fid = str(file_id).strip()
        if not fid.isdigit():
            raise ValueError(f"Invalid id: {file_id}")
        meta = self._get_json(f"/files/{fid}")
        url = meta.get("url") if isinstance(meta, dict) else None
        if not isinstance(url, str) or urlparse(url).scheme != "https":
            raise FileNotFoundError(file_id)
        name = str(
            meta.get("display_name") or meta.get("filename") or f"canvas-file-{fid}"
        )
        # `url` is pre-signed by Canvas — do NOT attach the bearer token.
        req = urllib.request.Request(url)
        try:
            data = self._transport(req)
        except Exception as e:
            raise CanvasError("Could not download the file from Canvas.") from e
        if len(data) > MAX_FILE_BYTES:
            raise CanvasError("Canvas file is too large.")
        return name, data

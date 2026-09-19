from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class TeamsItem:
    id: str
    name: str


class TeamsProvider(Protocol):
    """Interface for a Teams data source.

    IDs are opaque strings to the caller. A real implementation backed by
    Microsoft Graph can replace MockTeamsProvider without touching routers.
    """

    def list_teams(self) -> list[TeamsItem]: ...
    def list_channels(self, team_id: str) -> list[TeamsItem]: ...
    def list_files(self, channel_id: str) -> list[TeamsItem]: ...
    def read_file(self, file_id: str) -> tuple[str, bytes]: ...


class MockTeamsProvider:
    """Directory-backed fake Teams: root/<team>/<channel>/<file>.

    Item IDs are POSIX relative paths (e.g. "Biology 101/Lectures/cells.txt").
    """

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    def _resolve(self, rel_id: str) -> Path:
        p = (self.root / rel_id).resolve()
        if self.root != p and self.root not in p.parents:
            raise ValueError(f"Invalid id: {rel_id}")
        return p

    def _dirs(self, parent: Path, prefix: str) -> list[TeamsItem]:
        if not parent.is_dir():
            return []
        return [
            TeamsItem(id=f"{prefix}{d.name}", name=d.name)
            for d in sorted(parent.iterdir())
            if d.is_dir()
        ]

    def list_teams(self) -> list[TeamsItem]:
        return self._dirs(self.root, "")

    def list_channels(self, team_id: str) -> list[TeamsItem]:
        return self._dirs(self._resolve(team_id), f"{team_id}/")

    def list_files(self, channel_id: str) -> list[TeamsItem]:
        channel_dir = self._resolve(channel_id)
        if not channel_dir.is_dir():
            return []
        return [
            TeamsItem(id=f"{channel_id}/{f.name}", name=f.name)
            for f in sorted(channel_dir.iterdir())
            if f.is_file()
        ]

    def read_file(self, file_id: str) -> tuple[str, bytes]:
        p = self._resolve(file_id)
        if not p.is_file():
            raise FileNotFoundError(file_id)
        return p.name, p.read_bytes()

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="briefly-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["MOCK_TEAMS_DIR"] = str(_TMP / "mock_teams")
os.environ["ANTHROPIC_API_KEY"] = "test-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Artifact, ChatMessage, Source, SubjectSpace  # noqa: E402

MOCK_TEAMS_DIR = _TMP / "mock_teams"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.create_all(engine)
    yield
    from app.db import SessionLocal

    db = SessionLocal()
    for model in (ChatMessage, Source, Artifact, SubjectSpace):
        db.query(model).delete()
    db.commit()
    db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_teams_dir():
    return MOCK_TEAMS_DIR


class FakeBlock:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class FakeResponse:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class FakeMessages:
    """Queue-based fake of anthropic.messages. Pop responses in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def text_block(text):
    return FakeBlock("text", text=text)


def tool_use_block(name, input_, id_="tu_1"):
    return FakeBlock("tool_use", id=id_, name=name, input=input_)

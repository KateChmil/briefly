import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="briefly-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["MOCK_TEAMS_DIR"] = str(_TMP / "mock_teams")
os.environ["MOCK_CANVAS_DIR"] = str(_TMP / "mock_canvas")
# Never let a developer's real Canvas env turn tests into network calls.
os.environ["CANVAS_BASE_URL"] = ""
os.environ["CANVAS_TOKEN"] = ""
os.environ["ANTHROPIC_API_KEY"] = "test-key"
# Tests always use fake clients; never let a developer's real .env pick the provider.
os.environ["LLM_PROVIDER"] = "anthropic"
os.environ["GEMINI_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Artifact,
    CalendarEvent,
    ChatMessage,
    Source,
    StudySession,
    SubjectSpace,
    UserNote,
)

MOCK_TEAMS_DIR = _TMP / "mock_teams"
MOCK_CANVAS_DIR = _TMP / "mock_canvas"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.create_all(engine)
    yield
    from app.db import SessionLocal

    db = SessionLocal()
    for model in (
        ChatMessage, Source, Artifact, StudySession, CalendarEvent, UserNote, SubjectSpace
    ):
        db.query(model).delete()
    db.commit()
    db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_teams_dir():
    return MOCK_TEAMS_DIR


@pytest.fixture
def mock_canvas_dir():
    return MOCK_CANVAS_DIR


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


class RouterClient:
    """Fake Anthropic client that answers by call type, so parallel calls are safe.

    - forced tool call (generation)  -> `tools[tool_name]` (dict, list of dicts to
      use in order, or an Exception to raise)
    - chat call with tools           -> next item of `chat` (a FakeResponse)
    - plain call (notes)             -> `notes` text
    """

    def __init__(self, tools=None, chat=None, notes="# Notes\nCells..."):
        import threading

        self.tools = {k: (list(v) if isinstance(v, list) else v) for k, v in (tools or {}).items()}
        self.chat = list(chat or [])
        self.notes = notes
        self.calls = []
        self._lock = threading.Lock()
        self.messages = self

    def create(self, **kwargs):
        with self._lock:
            self.calls.append(kwargs)
            choice = kwargs.get("tool_choice")
            if choice:
                value = self.tools[choice["name"]]
                if isinstance(value, list):
                    value = value.pop(0)
                if isinstance(value, Exception):
                    raise value
                return FakeResponse(
                    [tool_use_block(choice["name"], value)], stop_reason="tool_use"
                )
            if kwargs.get("tools"):
                return self.chat.pop(0)
            if isinstance(self.notes, Exception):
                raise self.notes
            return FakeResponse([text_block(self.notes)])


def sample_tools(today=None, exam_in=10):
    """Valid structured outputs for all three forced-tool artifacts."""
    from datetime import date, timedelta

    today = today or date.today()
    return {
        "submit_study_plan": {
            "overview": "## Strategy\nStudy a little every day.",
            "sessions": [
                {
                    "date": (today + timedelta(days=d)).isoformat(),
                    "title": f"Session {d}",
                    "topic": "cells.txt",
                    "minutes": 45,
                    "kind": "study",
                }
                for d in (1, 3, 5)
            ],
        },
        "submit_sample_test": {
            "title": "Bio quiz",
            "questions": [
                {
                    "type": "mcq",
                    "question": f"Question {i}?",
                    "choices": ["Nucleus", "Mitochondria"],
                    "answer": "Mitochondria",
                    "explanation": "site of respiration",
                }
                for i in range(3)
            ],
        },
        "submit_flashcards": {
            "cards": [{"front": f"Term {i}", "back": f"Definition {i}"} for i in range(5)]
        },
    }

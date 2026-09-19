"""Gemini adapter: request/response translation, retries, errors, and a full app flow
driven through GeminiClient with a fake HTTP transport (no network, no API key)."""

import json
from datetime import date, timedelta

import pytest

from app.config import settings
from app.services import agent, generation, llm
from app.services.gemini import (
    GeminiClient,
    GeminiError,
    parse_response,
    to_gemini_contents,
    to_gemini_request,
    to_gemini_schema,
)
from app.services.llm_types import MalformedOutput
from tests.conftest import sample_tools

TOOL = {
    "name": "save_student_profile",
    "description": "Save the profile",
    "input_schema": {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "the goal"},
            "weekly_hours": {"type": "number"},
            "weak_topics": {"type": "array", "items": {"type": "string"}},
            "kind": {"type": "string", "enum": ["a", "b"]},
        },
        "required": ["goal"],
        "additionalProperties": False,
    },
}


def ok(parts, finish="STOP"):
    return 200, {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": finish}]}


class FakeTransport:
    """Scripted HTTP responses; records what was sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, url, headers, body, timeout):
        self.requests.append((url, headers, body))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(transport, **kw):
    sleeps = []
    client = GeminiClient("KEY", "gemini-test", transport=transport, sleep=sleeps.append, **kw)
    client.sleeps = sleeps
    return client


# ---- schema and request translation ---------------------------------------


def test_schema_is_converted_to_gemini_format():
    schema = to_gemini_schema(TOOL["input_schema"])
    assert schema["type"] == "OBJECT"
    assert schema["properties"]["goal"] == {"type": "STRING", "description": "the goal"}
    assert schema["properties"]["weak_topics"]["items"] == {"type": "STRING"}
    assert schema["properties"]["kind"]["enum"] == ["a", "b"]
    assert schema["required"] == ["goal"]
    assert "additionalProperties" not in schema  # unsupported by Gemini's Schema


def test_request_has_system_tools_and_forced_tool_choice():
    body = to_gemini_request(
        system="Be brief",
        messages=[{"role": "user", "content": "hi"}],
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "save_student_profile"},
        max_tokens=1000,
        thinking_budget=None,
        signatures={},
    )
    assert body["systemInstruction"] == {"parts": [{"text": "Be brief"}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]
    decl = body["tools"][0]["functionDeclarations"][0]
    assert decl["name"] == "save_student_profile" and decl["parameters"]["type"] == "OBJECT"
    assert body["toolConfig"] == {
        "functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": ["save_student_profile"]}
    }
    assert body["generationConfig"]["maxOutputTokens"] > 1000  # headroom for thinking
    assert "thinkingConfig" not in body["generationConfig"]


def test_no_tool_config_without_forced_choice_and_optional_thinking_budget():
    body = to_gemini_request(
        system=None, messages=[{"role": "user", "content": "hi"}], tools=[TOOL],
        tool_choice=None, max_tokens=100, thinking_budget=0, signatures={},
    )
    assert "toolConfig" not in body and "systemInstruction" not in body
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


def test_history_with_tool_round_trip_and_signature():
    messages = [
        {"role": "user", "content": "exam in 2 weeks"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Thanks!"},
                {"type": "tool_use", "id": "call_1", "name": "save_student_profile", "input": {"goal": "pass"}},
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "Profile saved."}],
        },
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "boom", "is_error": True}]},
        {"role": "assistant", "content": "   "},  # blank turns are dropped, Gemini rejects empty parts
    ]
    contents = to_gemini_contents(messages, {"call_1": "SIG"})
    assert [c["role"] for c in contents] == ["user", "model", "user", "user"]
    assert contents[1]["parts"][1] == {
        "functionCall": {"name": "save_student_profile", "args": {"goal": "pass"}},
        "thoughtSignature": "SIG",
    }
    assert contents[2]["parts"][0] == {
        "functionResponse": {"name": "save_student_profile", "response": {"result": "Profile saved."}}
    }
    assert contents[3]["parts"][0]["functionResponse"]["response"] == {"error": "boom"}


# ---- response translation --------------------------------------------------


def test_parse_text_and_function_call():
    sigs = {}
    resp = parse_response(
        ok([{"text": "Working on it."}, {"functionCall": {"name": "f", "args": {"x": 1}}, "thoughtSignature": "S"}])[1],
        sigs,
    )
    assert resp.stop_reason == "tool_use"
    text, call = resp.content
    assert (text.type, text.text) == ("text", "Working on it.")
    assert (call.type, call.name, call.input) == ("tool_use", "f", {"x": 1})
    assert sigs[call.id] == "S"  # remembered so it can be echoed back next turn


def test_parse_skips_thought_parts_and_handles_missing_args():
    resp = parse_response(
        ok([{"text": "hidden reasoning", "thought": True}, {"text": "Answer"}, {"functionCall": {"name": "g"}}])[1], {}
    )
    assert [b.type for b in resp.content] == ["text", "tool_use"]
    assert resp.content[0].text == "Answer" and resp.content[1].input == {}


@pytest.mark.parametrize(
    "payload,message",
    [
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "blocked"),
        ({"candidates": []}, "no answer"),
        (ok([], finish="SAFETY")[1], "SAFETY"),
    ],
)
def test_parse_errors_are_readable(payload, message):
    with pytest.raises(GeminiError, match=message):
        parse_response(payload, {})


def test_malformed_function_call_is_retryable_and_max_tokens_reported():
    with pytest.raises(MalformedOutput):
        parse_response(ok([], finish="MALFORMED_FUNCTION_CALL")[1], {})
    assert parse_response(ok([{"text": "cut off"}], finish="MAX_TOKENS")[1], {}).stop_reason == "max_tokens"
    assert parse_response(ok([])[1], {}).content == []  # a legitimately empty STOP reply


# ---- HTTP behaviour --------------------------------------------------------


def test_request_goes_to_generate_content_with_key_header():
    transport = FakeTransport(ok([{"text": "pong"}]))
    client = make_client(transport)
    resp = client.messages.create(model="ignored", system="s", messages=[{"role": "user", "content": "ping"}], max_tokens=50)
    assert resp.content[0].text == "pong"
    url, headers, _ = transport.requests[0]
    assert url.endswith("/models/gemini-test:generateContent")
    assert headers["x-goog-api-key"] == "KEY" and "KEY" not in url


def test_retries_rate_limits_then_succeeds():
    limited = (429, {"error": {"message": "slow down", "details": [{"retryDelay": "3s"}]}})
    transport = FakeTransport(limited, (503, {"error": {"message": "busy"}}), ok([{"text": "ok"}]))
    client = make_client(transport)
    resp = client.messages.create(messages=[{"role": "user", "content": "x"}])
    assert resp.content[0].text == "ok"
    assert client.sleeps == [3.0, 5.0]  # server hint first, then backoff


def test_daily_quota_fails_fast_with_helpful_message():
    quota = (429, {"error": {"message": "quota", "details": [{"retryDelay": "3600s"}]}})
    client = make_client(FakeTransport(quota))
    with pytest.raises(GeminiError, match="rate limit"):
        client.messages.create(messages=[{"role": "user", "content": "x"}])
    assert client.sleeps == []


def test_gives_up_after_repeated_failures():
    client = make_client(FakeTransport(*[(503, {"error": {"message": "busy"}})] * 4))
    with pytest.raises(GeminiError, match="503"):
        client.messages.create(messages=[{"role": "user", "content": "x"}])
    assert len(client.sleeps) == 3


@pytest.mark.parametrize(
    "status,payload,expected",
    [
        (400, {"error": {"message": "API key not valid. Please pass a valid API key."}}, "GEMINI_API_KEY"),
        (403, {"error": {"message": "permission denied"}}, "GEMINI_API_KEY"),
        (404, {"error": {"message": "model not found"}}, "GEMINI_MODEL"),
        (400, {"error": {"message": "Invalid JSON payload"}}, "Invalid JSON payload"),
    ],
)
def test_http_errors_have_actionable_messages(status, payload, expected):
    client = make_client(FakeTransport((status, payload)))
    with pytest.raises(GeminiError, match=expected):
        client.messages.create(messages=[{"role": "user", "content": "x"}])


def test_network_failure_is_retried_then_reported():
    client = make_client(FakeTransport(*[ConnectionError("down")] * 4))
    with pytest.raises(GeminiError, match="Could not reach Gemini"):
        client.messages.create(messages=[{"role": "user", "content": "x"}])


# ---- provider selection ----------------------------------------------------


def test_provider_selection(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    assert settings.provider == "anthropic"
    monkeypatch.setattr(settings, "gemini_api_key", "g")
    assert settings.provider == "gemini" and settings.model_name == settings.gemini_model
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    assert settings.provider == "anthropic"


def test_get_client_returns_gemini_or_explains_missing_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    llm.get_client.cache_clear()
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        llm.get_client()
    monkeypatch.setattr(settings, "gemini_api_key", "g")
    llm.get_client.cache_clear()
    client = llm.get_client()
    assert isinstance(client, GeminiClient) and client.model == settings.gemini_model
    llm.get_client.cache_clear()


# ---- the whole app through GeminiClient -----------------------------------


class FakeGeminiServer:
    """Answers like Gemini would, deciding by what the request asks for."""

    def __init__(self, chat_script):
        self.chat = list(chat_script)
        self.tools = sample_tools()
        self.requests = []

    def __call__(self, url, headers, body, timeout):
        self.requests.append(body)
        config = (body.get("toolConfig") or {}).get("functionCallingConfig", {})
        if config.get("allowedFunctionNames"):  # forced structured output
            name = config["allowedFunctionNames"][0]
            return ok([{"functionCall": {"name": name, "args": self.tools[name]}}])
        if body.get("tools"):  # chat turn with tools available
            return ok(self.chat.pop(0))
        return ok([{"text": "# Notes\nCells make ATP."}])  # notes


def test_full_interview_and_generation_flow_through_gemini(client, monkeypatch):
    exam = (date.today() + timedelta(days=10)).isoformat()
    server = FakeGeminiServer(
        [
            [{"text": "When is your exam?"}],
            [{"functionCall": {"name": "save_student_profile", "args": {"goal": "pass", "exam_date": exam}}, "thoughtSignature": "SIG"}],
            [{"text": "Generating your materials!"}],
        ]
    )
    gemini = make_client(server)
    monkeypatch.setattr(llm, "get_client", lambda: gemini)

    sid = client.post("/api/spaces", json={"name": "Bio"}).json()["id"]
    r1 = client.post(f"/api/spaces/{sid}/chat", json={"content": "hi"})
    assert r1.json()["message"]["content"] == "When is your exam?"

    r2 = client.post(f"/api/spaces/{sid}/chat", json={"content": "exam soon"})
    assert r2.json()["profile_completed"] is True
    assert r2.json()["message"]["content"] == "Generating your materials!"

    detail = client.get(f"/api/spaces/{sid}").json()
    assert detail["status"] == "ready" and detail["exam_date"] == exam
    kinds = {a["kind"] for a in client.get(f"/api/spaces/{sid}/artifacts").json()}
    assert kinds == {"study_plan", "notes", "sample_test", "flashcards"}
    assert len(client.get(f"/api/spaces/{sid}/sessions").json()) == 3

    # The turn after the tool call must echo the model's own functionCall + signature
    # and answer it with a functionResponse — Gemini 3 rejects the request otherwise.
    followup = next(b for b in server.requests if any(
        p.get("functionResponse") for c in b["contents"] for p in c["parts"]))
    model_turn = next(c for c in followup["contents"] if c["role"] == "model" and any("functionCall" in p for p in c["parts"]))
    call_part = next(p for p in model_turn["parts"] if "functionCall" in p)
    assert call_part["thoughtSignature"] == "SIG"
    response_part = followup["contents"][-1]["parts"][0]["functionResponse"]
    assert response_part["name"] == "save_student_profile"


def test_tutor_and_agent_work_with_gemini_blocks():
    server = FakeGeminiServer([[{"text": "Mitochondria make ATP."}]])
    gemini = make_client(server)
    space = type("S", (), {"name": "Bio", "sources": [], "profile": {"goal": "pass"}})()
    reply, changes = agent.run_tutor_turn(space, [{"role": "user", "content": "what makes ATP?"}], client=gemini)
    assert reply == "Mitochondria make ATP." and changes is None


def test_malformed_function_call_is_retried_once():
    bad = ok([], finish="MALFORMED_FUNCTION_CALL")
    good = ok([{"functionCall": {"name": "submit_flashcards", "args": sample_tools()["submit_flashcards"]}}])
    gemini = make_client(FakeTransport(bad, good))
    gen = generation.generate_artifact("ctx", generation.ArtifactKind.flashcards, client=gemini)
    assert json.loads(gen.content)["cards"][0]["front"] == "Term 0"


# ---- spreading generation across models (free keys: ~5 requests/min per model) --------


def fc(name="submit_flashcards", args=None):
    return ok([{"functionCall": {"name": name, "args": args or {}}, "thoughtSignature": "S"}])


def model_of(request):
    return request[0].split("/models/")[1].split(":")[0]


def pooled(transport, models=("m-a", "m-b", "m-c")):
    sleeps, now = [], [1000.0]
    client = GeminiClient(
        "KEY", models[0], fallback_models=list(models[1:]), transport=transport,
        sleep=lambda s: (sleeps.append(s), now.__setitem__(0, now[0] + s)), clock=lambda: now[0],
    )
    client.sleeps, client.now = sleeps, now
    return client


FORCED = {"type": "tool", "name": "submit_flashcards"}
CARDS_TOOL = {"name": "submit_flashcards", "description": "d", "input_schema": {"type": "object", "properties": {"cards": {"type": "array", "items": {"type": "object"}}}}}


def forced_call(client, text="x"):
    return client.messages.create(
        messages=[{"role": "user", "content": text}], tools=[CARDS_TOOL], tool_choice=FORCED
    )


def test_generation_calls_are_spread_across_models():
    transport = FakeTransport(*[fc() for _ in range(6)])
    client = pooled(transport)
    for _ in range(6):
        forced_call(client)
    used = [model_of(r) for r in transport.requests]
    assert {m: used.count(m) for m in set(used)} == {"m-a": 2, "m-b": 2, "m-c": 2}


def test_rate_limited_model_is_skipped_without_waiting():
    limited = (429, {"error": {"message": "quota", "details": [{"retryDelay": "30s"}]}})
    transport = FakeTransport(limited, fc(), fc(), fc())
    client = pooled(transport)
    forced_call(client)  # first pick is rate limited -> switches to another model at once
    assert client.sleeps == []
    first, second = (model_of(r) for r in transport.requests[:2])
    assert first != second
    for _ in range(2):
        forced_call(client)
    assert first not in [model_of(r) for r in transport.requests[2:]]  # cooling down


def test_all_models_limited_waits_the_suggested_delay():
    limited = (429, {"error": {"message": "quota", "details": [{"retryDelay": "20s"}]}})
    transport = FakeTransport(limited, limited, limited, fc())
    client = pooled(transport)
    forced_call(client)
    assert client.sleeps == [20.0]
    assert len(transport.requests) == 4


def test_retired_fallback_model_is_dropped():
    gone = (404, {"error": {"message": "no longer available to new users"}})
    seen = []

    def transport(url, headers, body, timeout):
        seen.append(model_of((url,)))
        return gone if seen[-1] == "m-b" else fc()

    client = pooled(transport, models=("m-a", "m-b"))
    for _ in range(4):
        forced_call(client)  # succeeds every time, even when the rotation lands on m-b
    assert "m-b" in client._dead
    assert seen[-2:] == ["m-a", "m-a"]  # and it is not tried again


def test_primary_model_404_shows_googles_message():
    gone = (404, {"error": {"message": "This model is no longer available to new users."}})
    client = pooled(FakeTransport(gone), models=("m-a",))
    with pytest.raises(GeminiError, match="no longer available to new users") as exc:
        forced_call(client)
    assert "GEMINI_MODEL" in str(exc.value)


def test_chat_calls_stay_on_the_primary_model():
    transport = FakeTransport(*[ok([{"text": "hi"}]) for _ in range(4)])
    client = pooled(transport)
    for _ in range(4):  # tools available but no forced choice = a chat turn
        client.messages.create(messages=[{"role": "user", "content": "hi"}], tools=[CARDS_TOOL])
    assert {model_of(r) for r in transport.requests} == {"m-a"}


def test_tool_conversation_is_pinned_to_the_model_that_made_the_call():
    transport = FakeTransport(fc(), fc(), ok([{"text": "done"}]))
    client = pooled(transport)
    forced_call(client)
    resp = forced_call(client)  # a different model: produces the tool call we continue with
    call = resp.content[0]
    client.messages.create(
        messages=[
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": call.id, "name": call.name, "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call.id, "content": "ok"}]},
        ],
        tools=[CARDS_TOOL],
    )
    # the follow-up went to the model that made the call, not to the default rotation pick
    assert model_of(transport.requests[2]) == model_of(transport.requests[1])
    assert model_of(transport.requests[1]) != model_of(transport.requests[0])

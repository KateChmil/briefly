"""Google Gemini backend for the app's LLM calls.

The rest of the backend (agent, generation) talks to the model in the shape of the
Anthropic Messages API: `client.messages.create(system=..., messages=[...],
tools=[...], tool_choice=...)` returning `.content` blocks of type `text` or
`tool_use`. `GeminiClient` accepts exactly that and translates it to Gemini's
`generateContent` REST API, so switching providers never touches the app logic.

It uses only the standard library (no SDK) and API key auth via the
`x-goog-api-key` header.
"""

import json
import re
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .llm_types import MalformedOutput, RetryableLLMError

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
RETRY_STATUSES = {429, 500, 502, 503, 504}
BACKOFF_SECONDS = (2.0, 5.0, 10.0)
MAX_RETRY_WAIT = 30.0
# Thinking tokens count against maxOutputTokens, so leave headroom for them.
THINKING_HEADROOM = 8192
MAX_OUTPUT_CAP = 32768
MAX_REMEMBERED_SIGNATURES = 2000


class GeminiError(RuntimeError):
    """A Gemini API failure with a message that is safe to show to the user."""


# Response objects shaped like the Anthropic SDK's, which is what the app expects.


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class Response:
    content: list = field(default_factory=list)
    stop_reason: str = "end_turn"


# --------------------------------------------------------------------------
# Request translation (pure functions, unit-tested)
# --------------------------------------------------------------------------

_SCHEMA_KEYS = {
    "type", "description", "enum", "items", "properties", "required", "format",
    "nullable", "minItems", "maxItems", "minimum", "maximum",
}


def to_gemini_schema(schema: Any) -> Any:
    """Convert a JSON-schema tool definition to Gemini's OpenAPI-style Schema."""
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in _SCHEMA_KEYS:
            continue
        if key == "type" and isinstance(value, str):
            out[key] = value.upper()
        elif key == "properties" and isinstance(value, dict):
            out[key] = {name: to_gemini_schema(sub) for name, sub in value.items()}
        elif key == "items":
            out[key] = to_gemini_schema(value)
        else:
            out[key] = value
    return out


def to_gemini_contents(messages: list[dict], signatures: dict[str, str]) -> list[dict]:
    """Anthropic-style messages -> Gemini `contents` (model/user turns with parts)."""
    tool_names: dict[str, str] = {}
    contents: list[dict] = []
    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"
        raw = message["content"]
        parts: list[dict] = []
        if isinstance(raw, str):
            if raw.strip():
                parts.append({"text": raw})
        else:
            for block in raw:
                kind = block.get("type")
                if kind == "text":
                    if block["text"].strip():
                        parts.append({"text": block["text"]})
                elif kind == "tool_use":
                    tool_names[block["id"]] = block["name"]
                    part: dict[str, Any] = {
                        "functionCall": {"name": block["name"], "args": block["input"]}
                    }
                    if signatures.get(block["id"]):
                        # Gemini 3 needs the model's own signature echoed back.
                        part["thoughtSignature"] = signatures[block["id"]]
                    parts.append(part)
                elif kind == "tool_result":
                    key = "error" if block.get("is_error") else "result"
                    parts.append(
                        {
                            "functionResponse": {
                                "name": tool_names.get(block["tool_use_id"], "tool"),
                                "response": {key: block["content"]},
                            }
                        }
                    )
        if parts:
            contents.append({"role": role, "parts": parts})
    return contents


def to_gemini_request(
    *,
    system: str | None,
    messages: list[dict],
    tools: list[dict] | None,
    tool_choice: dict | None,
    max_tokens: int,
    thinking_budget: int | None,
    signatures: dict[str, str],
) -> dict:
    body: dict[str, Any] = {
        "contents": to_gemini_contents(messages, signatures),
        "generationConfig": {
            "maxOutputTokens": min(max_tokens + THINKING_HEADROOM, MAX_OUTPUT_CAP),
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if thinking_budget is not None:
        body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": thinking_budget}
    if tools:
        body["tools"] = [
            {
                "functionDeclarations": [
                    {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": to_gemini_schema(t["input_schema"]),
                    }
                    for t in tools
                ]
            }
        ]
        choice = (tool_choice or {}).get("type")
        if choice == "tool":
            body["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": [tool_choice["name"]],
                }
            }
        elif choice == "any":
            body["toolConfig"] = {"functionCallingConfig": {"mode": "ANY"}}
    return body


# --------------------------------------------------------------------------
# Response translation
# --------------------------------------------------------------------------


def parse_response(data: dict, signatures: dict[str, str]) -> Response:
    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason")
        if reason:
            raise GeminiError(
                f"Gemini blocked the request ({reason}). Try rephrasing or using other files."
            )
        raise GeminiError("Gemini returned no answer.")

    candidate = candidates[0]
    finish = candidate.get("finishReason")
    blocks: list = []
    for part in (candidate.get("content") or {}).get("parts") or []:
        if part.get("thought"):  # a thought summary, not part of the answer
            continue
        if "functionCall" in part:
            call = part["functionCall"]
            call_id = f"call_{uuid.uuid4().hex[:12]}"
            if part.get("thoughtSignature"):
                if len(signatures) >= MAX_REMEMBERED_SIGNATURES:
                    signatures.clear()
                signatures[call_id] = part["thoughtSignature"]
            blocks.append(
                ToolUseBlock(id=call_id, name=call["name"], input=dict(call.get("args") or {}))
            )
        elif part.get("text"):
            blocks.append(TextBlock(text=part["text"]))

    if not blocks and finish not in (None, "STOP"):
        if finish == "MALFORMED_FUNCTION_CALL":
            raise MalformedOutput("Gemini produced a malformed function call.")
        raise GeminiError(f"Gemini stopped without an answer (finishReason={finish}).")

    if any(isinstance(b, ToolUseBlock) for b in blocks):
        stop = "tool_use"
    else:
        stop = "max_tokens" if finish == "MAX_TOKENS" else "end_turn"
    return Response(content=blocks, stop_reason=stop)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

Transport = Callable[[str, dict, dict, float], tuple[int, dict]]


def urllib_transport(url: str, headers: dict, body: dict, timeout: float) -> tuple[int, dict]:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"error": {"message": raw[:300]}}


def _retry_delay(payload: dict) -> float | None:
    """Server-suggested wait (RetryInfo.retryDelay, e.g. '31s') if present."""
    for detail in (payload.get("error") or {}).get("details") or []:
        match = re.fullmatch(r"([\d.]+)s", str(detail.get("retryDelay", "")))
        if match:
            return float(match.group(1))
    return None


def describe_http_error(status: int, payload: dict, model: str) -> GeminiError:
    message = str((payload.get("error") or {}).get("message", "")).strip()
    lowered = message.lower()
    if status in (400, 401, 403) and ("api key" in lowered or "api_key" in lowered or status != 400):
        return GeminiError(
            "Gemini rejected the API key. Check GEMINI_API_KEY in backend/.env "
            "and restart the backend."
        )
    if status == 404:
        return GeminiError(
            f"Gemini model '{model}' was not found. Set GEMINI_MODEL in backend/.env "
            "to a model listed in Google AI Studio."
        )
    if status == 429:
        return GeminiError(
            "Gemini rate limit reached (free keys allow only a few requests per minute "
            "and a daily quota). Wait a minute and try again."
        )
    return GeminiError(f"Gemini error {status}: {message[:200] or 'unknown error'}")


class GeminiClient:
    """Drop-in for the slice of the Anthropic client the app uses."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        thinking_budget: int | None = None,
        timeout: float = 120,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.thinking_budget = thinking_budget
        self.timeout = timeout
        self._transport = transport
        self._sleep = sleep
        self._signatures: dict[str, str] = {}
        self.messages = self  # so `client.messages.create(...)` works

    def create(
        self,
        *,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
        max_tokens: int = 4096,
        **_ignored: Any,  # e.g. `model`: the model is fixed per client
    ) -> Response:
        body = to_gemini_request(
            system=system,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
            thinking_budget=self.thinking_budget,
            signatures=self._signatures,
        )
        return parse_response(self._post(body), self._signatures)

    def _post(self, body: dict) -> dict:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        attempts = len(BACKOFF_SECONDS) + 1
        for attempt in range(attempts):
            last = attempt == attempts - 1
            try:
                status, payload = self._transport(url, headers, body, self.timeout)
            except (OSError, TimeoutError):
                if last:
                    raise GeminiError("Could not reach Gemini. Check your internet connection.")
                self._sleep(BACKOFF_SECONDS[attempt])
                continue
            if status == 200:
                return payload
            if status in RETRY_STATUSES and not last:
                wait = _retry_delay(payload)
                if wait is not None and wait > MAX_RETRY_WAIT:
                    raise describe_http_error(status, payload, self.model)  # quota, not a blip
                self._sleep(min(wait if wait is not None else BACKOFF_SECONDS[attempt], MAX_RETRY_WAIT))
                continue
            raise describe_http_error(status, payload, self.model)
        raise GeminiError("Gemini request failed.")  # unreachable

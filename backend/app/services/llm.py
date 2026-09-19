"""Provider-neutral entry point for LLM calls.

The app speaks the Anthropic Messages shape everywhere (see `gemini.py` for how a
Gemini backend plugs in). `get_client()` returns whichever provider is configured;
tests and callers may pass their own `client` to `create_message`.
"""

from functools import lru_cache

from ..config import settings
from .llm_types import MalformedOutput, RetryableLLMError  # noqa: F401  (re-exported)


@lru_cache
def get_client():
    if settings.provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Copy backend/.env.example to "
                "backend/.env and add your key."
            )
        from .gemini import GeminiClient

        return GeminiClient(
            settings.gemini_api_key,
            settings.gemini_model,
            base_url=settings.gemini_base_url,
            thinking_budget=settings.gemini_thinking_budget,
            fallback_models=settings.gemini_fallback_list,
        )

    if not settings.anthropic_api_key:
        raise RuntimeError(
            "No AI key is set. Add GEMINI_API_KEY (or ANTHROPIC_API_KEY) to "
            "backend/.env — copy backend/.env.example to get started."
        )
    from anthropic import Anthropic

    return Anthropic(api_key=settings.anthropic_api_key)


def create_message(
    *,
    system,
    messages,
    tools=None,
    tool_choice=None,
    max_tokens=4096,
    client=None,
):
    client = client or get_client()
    kwargs = {
        "model": settings.model_name,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    return client.messages.create(**kwargs)


def tool_input(resp, name: str) -> dict | None:
    """Input of the first tool_use block called `name`, if the model made one."""
    for block in resp.content:
        if block.type == "tool_use" and block.name == name:
            return dict(block.input)
    return None

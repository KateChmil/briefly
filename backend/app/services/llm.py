from functools import lru_cache

from anthropic import Anthropic

from ..config import settings


@lru_cache
def get_client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy backend/.env.example to "
            "backend/.env and add your key."
        )
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
        "model": settings.anthropic_model,
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

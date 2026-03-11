"""
OpenAI LLM client — uses the openai SDK with native async support.

Provides sync generate_completion() and async generate_completion_async().
"""
import asyncio
from typing import Any, Dict, List, Tuple

from openai import OpenAI, AsyncOpenAI

from .config import get_settings

settings = get_settings()

ChatMessageDict = Dict[str, str]

# Sync client (used in thread-pool fallback)
_sync_client = OpenAI(api_key=settings.openai_api_key)

# Async client (preferred — no thread pool needed)
_async_client = AsyncOpenAI(api_key=settings.openai_api_key)


def generate_completion(
    messages: List[ChatMessageDict],
    model: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, Dict[str, Any]]:
    """
    Call OpenAI chat completions (sync) and return (text, usage_dict).

    messages must be a list of {"role": ..., "content": ...} dicts.
    Roles supported: system, user, assistant — passed through as-is.
    """
    response = _sync_client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        max_tokens=max_tokens,
    )

    text = response.choices[0].message.content or ""

    usage: Dict[str, Any] = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
        "completion_tokens": response.usage.completion_tokens if response.usage else None,
        "total_tokens": response.usage.total_tokens if response.usage else None,
        "id": response.id,
    }

    return text, usage


async def generate_completion_async(
    messages: List[ChatMessageDict],
    model: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, Dict[str, Any]]:
    """Async OpenAI call — uses AsyncOpenAI client directly (no thread pool needed)."""
    response = await _async_client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        max_tokens=max_tokens,
    )

    text = response.choices[0].message.content or ""

    usage: Dict[str, Any] = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
        "completion_tokens": response.usage.completion_tokens if response.usage else None,
        "total_tokens": response.usage.total_tokens if response.usage else None,
        "id": response.id,
    }

    return text, usage

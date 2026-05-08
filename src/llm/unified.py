from __future__ import annotations

import asyncio
import os
import queue
import threading
from collections.abc import AsyncIterator, Sequence

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.llm import bedrock_sync
from src.logging_conf import log_event

load_dotenv(override=True)

OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")

CHAT_SYSTEM_DEFAULT = (
    "You are a helpful assistant. Answer clearly. Use markdown when it improves readability."
)


def _openai_messages(
    system: str,
    messages: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if system.strip():
        out.append({"role": "system", "content": system})
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role not in ("user", "assistant"):
            continue
        out.append({"role": role, "content": content})
    return out


async def llm_stream_chat(
    *,
    provider: str,
    model: str,
    messages: Sequence[dict[str, str]],
    system: str = CHAT_SYSTEM_DEFAULT,
) -> AsyncIterator[str]:
    """Stream assistant text deltas (OpenAI or Anthropic)."""
    p = provider.lower().strip()
    if p == "openai":
        if not OPENAI_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        client = AsyncOpenAI(api_key=OPENAI_KEY)
        stream = await client.chat.completions.create(
            model=model,
            messages=_openai_messages(system, messages),
            temperature=0.5,
            stream=True,
        )
        async for event in stream:
            chunk = event.choices[0].delta.content
            if chunk:
                yield chunk
        return

    if p == "anthropic":
        if not ANTHROPIC_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        client = AsyncAnthropic(api_key=ANTHROPIC_KEY)
        anth_msgs: list[dict[str, str]] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role not in ("user", "assistant"):
                continue
            anth_msgs.append({"role": role, "content": content})
        async with client.messages.stream(
            model=model,
            max_tokens=8192,
            system=system,
            messages=anth_msgs,  # type: ignore[arg-type]
        ) as stream:
            async for text in stream.text_stream:
                yield text
        return

    if p == "bedrock":
        bedrock_sync.require_bedrock_sdk()
        if not bedrock_sync.has_bedrock_credentials():
            raise RuntimeError(
                "No AWS credentials for Bedrock. Set AWS_BEARER_TOKEN_BEDROCK (Bedrock API key), "
                "or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_DEFAULT_REGION, or AWS_PROFILE, in .env."
            )
        sq: queue.SimpleQueue[object] = queue.SimpleQueue()
        th = threading.Thread(
            target=bedrock_sync.run_converse_stream_to_queue,
            kwargs={
                "model_id": model,
                "system": system,
                "messages": messages,
                "temperature": 0.5,
                "sq": sq,
            },
            daemon=True,
        )
        th.start()
        while True:
            item = await asyncio.to_thread(sq.get)
            if item is None:
                break
            if isinstance(item, BaseException):
                raise RuntimeError(str(item)) from item
            yield str(item)
        th.join(timeout=5.0)
        return

    raise ValueError(f"Unknown provider: {provider}")


async def llm_complete(
    *,
    provider: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.3,
) -> str:
    """Single-turn completion (used by resume stages)."""
    p = provider.lower().strip()
    if p == "openai":
        if not OPENAI_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        client = AsyncOpenAI(api_key=OPENAI_KEY)
        r = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return (r.choices[0].message.content or "").strip()

    if p == "anthropic":
        if not ANTHROPIC_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        client = AsyncAnthropic(api_key=ANTHROPIC_KEY)
        r = await client.messages.create(
            model=model,
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts: list[str] = []
        for block in r.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "".join(parts).strip()

    if p == "bedrock":
        bedrock_sync.require_bedrock_sdk()
        if not bedrock_sync.has_bedrock_credentials():
            raise RuntimeError(
                "No AWS credentials for Bedrock. Set AWS_BEARER_TOKEN_BEDROCK (Bedrock API key), "
                "or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_DEFAULT_REGION, or AWS_PROFILE, in .env."
            )
        return await asyncio.to_thread(
            lambda: bedrock_sync.converse_complete(
                model_id=model,
                system=system,
                user=user,
                temperature=temperature,
            ),
        )

    raise ValueError(f"Unknown provider: {provider}")


async def llm_complete_logged(
    *,
    stage: str,
    provider: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.3,
) -> str:
    try:
        out = await llm_complete(
            provider=provider, model=model, system=system, user=user, temperature=temperature
        )
        log_event("llm_complete_ok", stage=stage, provider=provider, model=model)
        return out
    except Exception as e:
        log_event("llm_complete_err", stage=stage, error=str(e))
        raise

"""Sync Amazon Bedrock Converse helpers — shared by `unified.py` (async chat) and `clients.py` (panel)."""

from __future__ import annotations

import os
import queue
from collections.abc import Sequence


def require_bedrock_sdk() -> None:
    """Raise with install hint if boto3 is not installed (optional dep until Bedrock is used)."""
    try:
        import boto3  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "Amazon Bedrock requires boto3. From your project venv run: pip install boto3"
        ) from e


def bedrock_region() -> str:
    return (
        os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or "us-east-1"
    )


def bedrock_client():
    require_bedrock_sdk()
    import boto3

    return boto3.client("bedrock-runtime", region_name=bedrock_region())


def _anthropic_profile_fallback_model_id(model_id: str, err: Exception) -> str | None:
    """Convert Anthropic foundation-model IDs to regional profile IDs when required."""
    if not model_id.startswith("anthropic.") or model_id.startswith("us.anthropic."):
        return None
    msg = str(err).lower()
    if "on-demand throughput isn't supported" not in msg and "on-demand throughput isn" not in msg:
        return None
    return f"us.{model_id}"


def has_bedrock_credentials() -> bool:
    """True if boto3 has credentials or AWS_BEARER_TOKEN_BEDROCK is set (Bedrock API keys)."""
    if os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip():
        return True
    try:
        import boto3
    except ImportError:
        return False
    return boto3.Session().get_credentials() is not None


def messages_to_bedrock(messages: Sequence[dict[str, str]]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role not in ("user", "assistant"):
            continue
        out.append({"role": role, "content": [{"text": content}]})
    return out


def _str_field(d: object, *keys: str) -> str | None:
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d:
            v = d[k]
            if isinstance(v, str) and v:
                return v
    return None


def _text_from_reasoning_delta(d: dict) -> str | None:
    """Streaming deltas use reasoningContent unions (often without top-level delta.text)."""
    rc = d.get("reasoningContent") or d.get("ReasoningContent")
    if not isinstance(rc, dict):
        return None
    t = _str_field(rc, "text", "Text")
    if t is not None:
        return t
    rt = rc.get("reasoningText") or rc.get("ReasoningText")
    if isinstance(rt, dict):
        return _str_field(rt, "text", "Text")
    return None


def _text_from_delta_union(d: dict) -> str | None:
    t = _str_field(d, "text", "Text")
    if t is not None:
        return t
    return _text_from_reasoning_delta(d)


def _text_from_output_content_block(block: object) -> tuple[str | None, str | None]:
    """Return (visible_text, reasoning_text); one side may be None."""
    if not isinstance(block, dict):
        return (None, None)
    tv = _str_field(block, "text", "Text")
    if tv is not None:
        return (tv, None)
    rc = block.get("reasoningContent") or block.get("ReasoningContent")
    if isinstance(rc, dict):
        rt = rc.get("reasoningText") or rc.get("ReasoningText")
        if isinstance(rt, dict):
            tr = _str_field(rt, "text", "Text")
            if tr is not None:
                return (None, tr)
        tr2 = _str_field(rc, "text", "Text")
        if tr2 is not None:
            return (None, tr2)
    return (None, None)


def _text_from_converse_output(r: dict) -> str:
    msg = (r.get("output") or {}).get("message") or {}
    plain_parts: list[str] = []
    reasoning_parts: list[str] = []
    for block in msg.get("content") or []:
        vis, rst = _text_from_output_content_block(block)
        if vis is not None:
            plain_parts.append(vis)
        if rst is not None:
            reasoning_parts.append(rst)
    out = "".join(plain_parts).strip()
    if out:
        return out
    return "".join(reasoning_parts).strip()


_STREAM_ERROR_KEYS = (
    "internalServerException",
    "modelStreamErrorException",
    "throttlingException",
    "validationException",
    "serviceUnavailableException",
    "accessDeniedException",
)


def stream_error_from_event(chunk: dict) -> Exception | None:
    for k in _STREAM_ERROR_KEYS:
        if k not in chunk:
            continue
        inner = chunk[k]
        if isinstance(inner, dict):
            msg = inner.get("message", repr(inner))
        else:
            msg = str(inner)
        return RuntimeError(f"Bedrock stream ({k}): {msg}")
    return None


def stream_delta(chunk: object, _depth: int = 0) -> str | None:
    """Extract incremental text from a ConverseStream event (shape varies by model/SDK)."""
    if _depth > 14:
        return None
    if not isinstance(chunk, dict):
        return None
    for cb_key in ("contentBlockDelta", "content_block_delta", "ContentBlockDelta"):
        cb = chunk.get(cb_key)
        if not isinstance(cb, dict):
            continue
        d = cb.get("delta") or cb.get("Delta") or {}
        if isinstance(d, dict):
            merged = _text_from_delta_union(d)
            if merged:
                return merged
    inner = chunk.get("chunk")
    if isinstance(inner, dict):
        return stream_delta(inner, _depth + 1)
    # Some wrappers nest stream payload once more
    for key in ("modelStreamErrorException", "message"):
        if key in chunk and isinstance(chunk[key], dict):
            t = stream_delta(chunk[key], _depth + 1)
            if t:
                return t
    return None


def converse_messages(
    *,
    model_id: str,
    system: str,
    messages: Sequence[dict[str, str]],
    temperature: float,
) -> str:
    """Non-streaming multi-turn completion (used as fallback when stream yields no text)."""
    from botocore.exceptions import BotoCoreError, ClientError

    client = bedrock_client()
    kwargs_base: dict = {
        "modelId": model_id,
        "messages": messages_to_bedrock(messages),
        "inferenceConfig": {"maxTokens": 8192, "temperature": temperature},
    }
    if system.strip():
        kwargs_base["system"] = [{"text": system}]
    kwargs = dict(kwargs_base)
    try:
        r = client.converse(**kwargs)
        return _text_from_converse_output(r)
    except (ClientError, BotoCoreError) as e:
        fallback = _anthropic_profile_fallback_model_id(model_id, e)
        if fallback is None:
            raise
        kwargs["modelId"] = fallback
        r = client.converse(**kwargs)
        return _text_from_converse_output(r)


def run_converse_stream_to_queue(
    *,
    model_id: str,
    system: str,
    messages: Sequence[dict[str, str]],
    temperature: float,
    sq: queue.SimpleQueue,
) -> None:
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        client = bedrock_client()
        kwargs: dict = {
            "modelId": model_id,
            "messages": messages_to_bedrock(messages),
            "inferenceConfig": {"maxTokens": 8192, "temperature": temperature},
        }
        if system.strip():
            kwargs["system"] = [{"text": system}]
        try:
            resp = client.converse_stream(**kwargs)
        except (ClientError, BotoCoreError) as e:
            fallback = _anthropic_profile_fallback_model_id(model_id, e)
            if fallback is None:
                raise
            kwargs["modelId"] = fallback
            resp = client.converse_stream(**kwargs)
        stream = resp.get("stream")
        if stream is None:
            sq.put(RuntimeError("Bedrock converse_stream response had no 'stream' body"))
            sq.put(None)
            return

        saw_output = False
        for event in stream:
            if not isinstance(event, dict):
                continue
            err = stream_error_from_event(event)
            if err is not None:
                sq.put(err)
                return
            t = stream_delta(event)
            if t:
                saw_output = True
                sq.put(t)

        # Stream parsed nothing (wrong delta shape, silent model, etc.) — try one-shot Converse.
        if not saw_output:
            full = converse_messages(
                model_id=model_id,
                system=system,
                messages=messages,
                temperature=temperature,
            )
            if full:
                sq.put(full)
        sq.put(None)
    except (ClientError, BotoCoreError, OSError, ValueError, KeyError, RuntimeError) as e:
        sq.put(e)


def converse_complete(
    *,
    model_id: str,
    system: str,
    user: str,
    temperature: float,
) -> str:
    from botocore.exceptions import BotoCoreError, ClientError

    client = bedrock_client()
    kwargs: dict = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": user}]}],
        "inferenceConfig": {"maxTokens": 8192, "temperature": temperature},
    }
    if system.strip():
        kwargs["system"] = [{"text": system}]
    try:
        r = client.converse(**kwargs)
        return _text_from_converse_output(r)
    except (ClientError, BotoCoreError) as e:
        fallback = _anthropic_profile_fallback_model_id(model_id, e)
        if fallback is None:
            raise
        kwargs["modelId"] = fallback
        r = client.converse(**kwargs)
        return _text_from_converse_output(r)

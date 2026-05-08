"""Optional token estimates for cost / context control."""

from __future__ import annotations

try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore[assignment]


def estimate_tokens(text: str, model: str = "gpt-4o-mini") -> int | None:
    if not text or tiktoken is None:
        return None
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

from src.llm import bedrock_sync

load_dotenv(override=True)


class LLMBackend(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class OpenAIBackend(LLMBackend):
    def __init__(self, model: str) -> None:
        self._model = model
        self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def complete(self, system: str, user: str) -> str:
        r = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
        )
        return (r.choices[0].message.content or "").strip()


class AnthropicBackend(LLMBackend):
    def __init__(self, model: str) -> None:
        self._model = model
        self._client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def complete(self, system: str, user: str) -> str:
        r = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts: list[str] = []
        for block in r.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "".join(parts).strip()


class BedrockBackend(LLMBackend):
    """Amazon Bedrock (sync Converse) — same env as unified chat: Bearer key or IAM / profile."""

    def __init__(self, model: str) -> None:
        self._model = model

    def complete(self, system: str, user: str) -> str:
        bedrock_sync.require_bedrock_sdk()
        if not bedrock_sync.has_bedrock_credentials():
            raise RuntimeError(
                "No AWS credentials for Bedrock. Set AWS_BEARER_TOKEN_BEDROCK (Bedrock API key), "
                "or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_DEFAULT_REGION, or AWS_PROFILE, in .env."
            )
        return bedrock_sync.converse_complete(
            model_id=self._model,
            system=system,
            user=user,
            temperature=0.4,
        )


def get_backend(provider: str, model: str) -> LLMBackend:
    p = provider.lower().strip()
    if p == "openai":
        return OpenAIBackend(model)
    if p == "anthropic":
        return AnthropicBackend(model)
    if p == "bedrock":
        return BedrockBackend(model)
    raise ValueError(f"Unknown provider: {provider}")

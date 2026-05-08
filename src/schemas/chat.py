from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    chat_id: str | None = Field(default=None, description="Existing chat; omit to create one")
    messages: list[ChatMessage] = Field(..., min_length=1)


class ChatCreatedResponse(BaseModel):
    chat_id: str

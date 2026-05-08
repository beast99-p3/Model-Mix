from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.config import CHAT_MODEL, CHAT_PROVIDER
from src.db import append_message, ensure_chat, init_db, replace_messages
from src.llm.unified import llm_stream_chat
from src.api.sse import sse_data
from src.schemas.chat import ChatRequest

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    init_db()
    msgs_in = [{"role": m.role, "content": m.content} for m in body.messages]
    if not msgs_in or msgs_in[-1]["role"] != "user":
        raise HTTPException(
            status_code=400,
            detail="Last message must be from the user.",
        )

    cid = ensure_chat(body.chat_id)
    replace_messages(cid, msgs_in)

    async def event_gen():
        yield sse_data({"type": "chat_id", "chat_id": cid})
        buf: list[str] = []
        try:
            async for delta in llm_stream_chat(
                provider=CHAT_PROVIDER,
                model=CHAT_MODEL,
                messages=msgs_in,
            ):
                buf.append(delta)
                yield sse_data({"type": "delta", "text": delta})
        except Exception as e:
            yield sse_data({"type": "error", "message": str(e)})
            return
        full = "".join(buf)
        append_message(cid, "assistant", full)
        yield sse_data({"type": "done"})

    return StreamingResponse(event_gen(), media_type="text/event-stream")

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from src.debate import run_debate
from src.schemas.debate import DebateAnalytics, DebateRequest, DebateResponse, DebaterScore, TranscriptEntry

router = APIRouter(prefix="/api", tags=["debate"])


@router.post("/debate", response_model=DebateResponse)
async def debate_endpoint(body: DebateRequest) -> DebateResponse:
    q = body.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        result = await asyncio.to_thread(run_debate, q)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Debate failed: {e!s}. Check API keys and model names in .env / src/config.py.",
        ) from e

    transcript = None
    if body.show_transcript:
        transcript = [
            TranscriptEntry(debater_id=t.debater_id, round_name=t.round_name, text=t.text)
            for t in result.transcript
        ]
    analytics = None
    if result.analytics is not None:
        analytics = DebateAnalytics(
            final_confidence_pct=result.analytics.final_confidence_pct,
            consensus_pct=result.analytics.consensus_pct,
            chair_provider=result.analytics.chair_provider,
            chair_model=result.analytics.chair_model,
            debaters=[
                DebaterScore(
                    debater_id=d.debater_id,
                    display_name=d.display_name,
                    provider=d.provider,
                    model=d.model,
                    contribution_pct=d.contribution_pct,
                    question_alignment_pct=d.question_alignment_pct,
                    final_overlap_pct=d.final_overlap_pct,
                    round2_length=d.round2_length,
                )
                for d in result.analytics.debaters
            ],
        )
    return DebateResponse(final_answer=result.final_answer, transcript=transcript, analytics=analytics)

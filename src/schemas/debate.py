from __future__ import annotations

from pydantic import BaseModel, Field


class DebateRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")
    show_transcript: bool = Field(
        default=False,
        description="Include round-by-round panel text in the response",
    )


class TranscriptEntry(BaseModel):
    debater_id: str
    round_name: str
    text: str


class DebaterScore(BaseModel):
    debater_id: str
    display_name: str
    provider: str
    model: str
    contribution_pct: float
    question_alignment_pct: float
    final_overlap_pct: float
    round2_length: int


class DebateAnalytics(BaseModel):
    final_confidence_pct: float
    consensus_pct: float
    chair_provider: str
    chair_model: str
    debaters: list[DebaterScore]


class DebateResponse(BaseModel):
    final_answer: str
    transcript: list[TranscriptEntry] | None = None
    analytics: DebateAnalytics | None = None

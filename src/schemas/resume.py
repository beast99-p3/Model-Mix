from __future__ import annotations

from pydantic import BaseModel, Field


class KeywordHit(BaseModel):
    keyword: str
    found_in_resume: bool = False


class AtsMatchScore(BaseModel):
    """Estimated ATS pass similarity for a resume vs a job description."""

    score_pct: float = Field(..., ge=0, le=100, description="Overall ATS match 0–100%")
    keyword_coverage_pct: float = Field(0, ge=0, le=100)
    jd_alignment_pct: float = Field(0, ge=0, le=100)
    gap_readiness_pct: float = Field(0, ge=0, le=100)
    keywords_matched: int = 0
    keywords_total: int = 0
    gaps_count: int = 0
    label: str = ""
    summary: str = ""
    keyword_hits: list[KeywordHit] = Field(default_factory=list)


class ResumeAnalyzeResponse(BaseModel):
    jd_keywords: list[str] = Field(default_factory=list)
    keyword_hits: list[KeywordHit] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    ats_match: AtsMatchScore | None = None
    resume_excerpt: str = Field(
        default="",
        description="Short plain-text preview of extracted resume (not full doc)",
    )
    resume_text: str = Field(
        default="",
        description="Full plain text extracted from the upload (for tailoring / diff in UI)",
    )
    source_upload_id: str | None = Field(
        default=None,
        description="ID of stored source file for format-preserving export",
    )


class ResumeGenerateRequest(BaseModel):
    resume_text: str = Field(..., min_length=20)
    jd_text: str = Field(..., min_length=20)
    preferences: str | None = Field(
        default=None,
        description="Optional user notes: tone, emphasis, one-page, etc.",
    )
    keywords: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    source_upload_id: str | None = Field(default=None)


class ResumeGenerateComplete(BaseModel):
    artifact_id: str
    message: str = "ok"


class ResumeRefineRequest(BaseModel):
    artifact_id: str = Field(..., min_length=8)
    feedback: str = Field(..., min_length=3)
    resume_text: str | None = Field(
        default=None,
        description="If omitted, server loads text from artifact metadata",
    )
    jd_text: str | None = Field(default=None)
    keywords: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class ResumeRefineResponse(BaseModel):
    artifact_id: str
    draft_markdown: str = ""
    ats_match: AtsMatchScore | None = None
    message: str = "ok"


class ResumeSaveRequest(BaseModel):
    artifact_id: str = Field(..., min_length=8)
    draft_markdown: str = Field(..., min_length=1)


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str | None = None
    error: str | None = None
    artifact_id: str | None = None

from __future__ import annotations

from pydantic import BaseModel, Field


class KeywordHit(BaseModel):
    keyword: str
    found_in_resume: bool = False


class ResumeAnalyzeResponse(BaseModel):
    jd_keywords: list[str] = Field(default_factory=list)
    keyword_hits: list[KeywordHit] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    resume_excerpt: str = Field(
        default="",
        description="Short plain-text preview of extracted resume (not full doc)",
    )
    resume_text: str = Field(
        default="",
        description="Full plain text extracted from the upload (for tailoring / diff in UI)",
    )


class ResumeGenerateRequest(BaseModel):
    resume_text: str = Field(..., min_length=20)
    jd_text: str = Field(..., min_length=20)
    preferences: str | None = Field(
        default=None,
        description="Optional user notes: tone, emphasis, one-page, etc.",
    )
    keywords: list[str] = Field(default_factory=list)


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


class ResumeRefineResponse(BaseModel):
    artifact_id: str
    message: str = "ok"


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str | None = None
    error: str | None = None
    artifact_id: str | None = None

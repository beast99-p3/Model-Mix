from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from src.config import (
    RESUME_ANALYZE_MODEL,
    RESUME_ANALYZE_PROVIDER,
    RESUME_DRAFT_MODEL,
    RESUME_DRAFT_PROVIDER,
    RESUME_REFINE_MODEL,
    RESUME_REFINE_PROVIDER,
)
from src.llm.unified import llm_complete_logged
from src.logging_conf import log_event
from src.schemas.resume import KeywordHit, ResumeAnalyzeResponse


@dataclass
class PipelineContext:
    resume_text: str
    jd_text: str
    preferences: str | None = None
    keywords: list[str] | None = None
    draft_markdown: str | None = None


ANALYZE_SYSTEM = """You analyze a job description and resume for ATS-style alignment.
Return ONLY valid JSON with keys:
- jd_keywords: array of 8-15 important keywords or short phrases from the JD (skills, tools, domains)
- gaps: array of 3-8 concise bullets describing what is missing or weak in the resume vs the JD
Do not include markdown fences or commentary."""


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def analyze_resume_jd(resume_text: str, jd_text: str) -> ResumeAnalyzeResponse:
    user = f"JOB DESCRIPTION:\n{jd_text[:12000]}\n\nRESUME:\n{resume_text[:12000]}"
    raw = await llm_complete_logged(
        stage="resume_analyze",
        provider=RESUME_ANALYZE_PROVIDER,
        model=RESUME_ANALYZE_MODEL,
        system=ANALYZE_SYSTEM,
        user=user,
        temperature=0.2,
    )
    try:
        data = _extract_json_object(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        data = {
            "jd_keywords": [],
            "gaps": ["Analyzer returned non-JSON; retry or shorten inputs."],
        }
    keywords = [str(x) for x in data.get("jd_keywords", [])]
    gaps = [str(x) for x in data.get("gaps", [])]
    lowered = resume_text.lower()
    hits = [
        KeywordHit(keyword=k, found_in_resume=k.lower() in lowered) for k in keywords
    ]
    excerpt = resume_text[:2000] + ("…" if len(resume_text) > 2000 else "")
    return ResumeAnalyzeResponse(
        jd_keywords=keywords,
        keyword_hits=hits,
        gaps=gaps,
        resume_excerpt=excerpt,
        resume_text=resume_text,
    )


DRAFT_SYSTEM = """You rewrite the candidate's resume to fit the job description.
Output markdown with clear sections (e.g. Summary, Experience, Skills, Education).
Use strong alignment to the JD keywords where truthful; do not invent employers, degrees, or dates.
Keep content concise and scannable. If preferences are given, honor them."""


async def draft_resume(ctx: PipelineContext) -> str:
    kw = ", ".join(ctx.keywords or [])
    pref = ctx.preferences or ""
    user = (
        f"Preferences:\n{pref}\n\n"
        f"Target keywords (use where accurate):\n{kw}\n\n"
        f"JOB DESCRIPTION:\n{ctx.jd_text[:12000]}\n\n"
        f"CURRENT RESUME:\n{ctx.resume_text[:12000]}\n\n"
        "Produce the rewritten resume in markdown."
    )
    return await llm_complete_logged(
        stage="resume_draft",
        provider=RESUME_DRAFT_PROVIDER,
        model=RESUME_DRAFT_MODEL,
        system=DRAFT_SYSTEM,
        user=user,
        temperature=0.35,
    )


REFINE_SYSTEM = """You edit an existing resume draft based on user feedback.
Return markdown only. Preserve factual content unless the user asks to rephrase.
Do not add fabricated employers, titles, or dates."""


async def refine_resume(
    *,
    draft_markdown: str,
    jd_text: str,
    feedback: str,
) -> str:
    user = (
        f"JOB DESCRIPTION (context):\n{jd_text[:8000]}\n\n"
        f"CURRENT DRAFT:\n{draft_markdown[:12000]}\n\n"
        f"USER FEEDBACK:\n{feedback}\n\n"
        "Return the full revised resume in markdown."
    )
    return await llm_complete_logged(
        stage="resume_refine",
        provider=RESUME_REFINE_PROVIDER,
        model=RESUME_REFINE_MODEL,
        system=REFINE_SYSTEM,
        user=user,
        temperature=0.25,
    )


def keyword_coverage_score(resume_text: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    low = resume_text.lower()
    hit = sum(1 for k in keywords if k.lower() in low)
    return hit / len(keywords)


def log_stage(stage: str, **fields: Any) -> None:
    log_event("resume_stage", stage=stage, **fields)

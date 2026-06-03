from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

from src.config import (
    RESUME_ANALYZE_MODEL,
    RESUME_ANALYZE_PROVIDER,
    RESUME_REFINE_MODEL,
    RESUME_REFINE_PROVIDER,
)
from src.debate import RESUME_FUSION_PROMPTS, StageCallback, run_fusion
from src.llm.unified import llm_complete_logged
from src.logging_conf import log_event
from src.resume.format import finalize_resume_output, line_count
from src.resume.ats_score import compute_ats_match, keyword_coverage_pct, keyword_in_resume
from src.schemas.resume import AtsMatchScore, KeywordHit, ResumeAnalyzeResponse


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
    hits = [
        KeywordHit(keyword=k, found_in_resume=keyword_in_resume(k, resume_text))
        for k in keywords
    ]
    excerpt = resume_text[:2000] + ("…" if len(resume_text) > 2000 else "")
    ats = compute_ats_match(
        resume_text=resume_text,
        jd_text=jd_text,
        keywords=keywords,
        gaps=gaps,
        keyword_hits=hits,
    )
    return ResumeAnalyzeResponse(
        jd_keywords=keywords,
        keyword_hits=hits,
        gaps=gaps,
        resume_excerpt=excerpt,
        resume_text=resume_text,
        ats_match=ats,
    )



def _build_resume_fusion_task(ctx: PipelineContext) -> str:
    kw = ", ".join(ctx.keywords or [])
    pref = ctx.preferences or "(none)"
    lines = line_count(ctx.resume_text)
    return (
        "Tailor this resume for the job description below.\n"
        "FORMAT RULES (mandatory unless preferences say otherwise):\n"
        "- Keep the same line-for-line structure as the source (same blank lines, bullets, indentation, tables).\n"
        "- Edit wording only; do not restructure or rename sections.\n"
        "- Preserve table rows (cells separated by |).\n"
        "- No AI-style headings like 'Selected Projects', 'Core Competencies', or 'Section Keywords'.\n"
        "- Sound human and professional, not templated.\n"
        "- Return ONLY the resume text — no commentary, planning, or line-count notes.\n\n"
        f"Preferences: {pref}\n"
        f"Target keywords (use naturally where accurate): {kw}\n\n"
        f"JOB DESCRIPTION:\n{ctx.jd_text[:12000]}\n\n"
        f"SOURCE RESUME ({lines} lines — mirror structure exactly):\n{ctx.resume_text[:12000]}"
    )


async def draft_resume(ctx: PipelineContext, on_stage: StageCallback | None = None) -> str:
    task = _build_resume_fusion_task(ctx)
    result = await asyncio.to_thread(
        run_fusion,
        task,
        RESUME_FUSION_PROMPTS,
        on_stage,
    )
    log_event(
        "resume_fusion_complete",
        confidence=result.analytics.final_confidence_pct if result.analytics else None,
        consensus=result.analytics.consensus_pct if result.analytics else None,
    )
    return finalize_resume_output(ctx.resume_text, result.final_answer)


REFINE_SYSTEM = """You edit a resume copy based on user feedback only.
Return ONLY the full revised resume text — no commentary, planning, or line-count notes.
Preserve factual content unless the user asks to rephrase. Do not add fabricated employers, titles, or dates.

Format rules (mandatory unless the user explicitly asks to change layout):
- Match the ORIGINAL RESUME FORMAT reference line-for-line (same blank lines, bullets, spacing).
- Do not add AI-style headings or rename sections.
- Preserve table rows (cells separated by |)."""


async def refine_resume(
    *,
    draft_markdown: str,
    jd_text: str,
    feedback: str,
    original_resume_text: str | None = None,
) -> str:
    original = (original_resume_text or draft_markdown).strip()
    user = (
        f"ORIGINAL RESUME FORMAT REFERENCE (preserve this structure):\n{original[:12000]}\n\n"
        f"JOB DESCRIPTION (context):\n{jd_text[:8000]}\n\n"
        f"CURRENT DRAFT TO EDIT:\n{draft_markdown[:12000]}\n\n"
        f"USER EDIT COMMAND:\n{feedback}\n\n"
        "Return the full revised resume text with format preserved."
    )
    raw = await llm_complete_logged(
        stage="resume_refine",
        provider=RESUME_REFINE_PROVIDER,
        model=RESUME_REFINE_MODEL,
        system=REFINE_SYSTEM,
        user=user,
        temperature=0.25,
    )
    return finalize_resume_output(original, raw)


def keyword_coverage_score(resume_text: str, keywords: list[str]) -> float:
    """Legacy 0–1 score; prefer compute_ats_match()."""
    return keyword_coverage_pct(resume_text, keywords) / 100.0


def compute_tailored_ats_match(
    *,
    resume_text: str,
    jd_text: str,
    keywords: list[str],
    gaps: list[str],
) -> AtsMatchScore:
    return compute_ats_match(
        resume_text=resume_text,
        jd_text=jd_text,
        keywords=keywords,
        gaps=gaps,
    )


def log_stage(stage: str, **fields: Any) -> None:
    log_event("resume_stage", stage=stage, **fields)

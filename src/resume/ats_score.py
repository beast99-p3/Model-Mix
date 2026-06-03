from __future__ import annotations

import re
from dataclasses import dataclass

from src.schemas.resume import AtsMatchScore, KeywordHit

_JD_STOP = frozenset(
    """
    a an the and or but in on at to for of with by from as is are was were be been being
    have has had do does did will would should could may might must can this that these those
    you your we our they their it its i me my he she him her us them not no yes all any each
    other than into over under about through during before after while when where how what which
    who whom whose why if then than so such very just also only even more most much many few
    role position job team work experience required preferred responsibilities qualifications
    ability abilities skills skill using use used using including include includes
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9+#][a-z0-9+#./-]*", re.I)


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 2 and t.lower() not in _JD_STOP}


def keyword_in_resume(keyword: str, resume_text: str) -> bool:
    k = keyword.lower().strip()
    if not k:
        return False
    low = resume_text.lower()
    if k in low:
        return True
    parts = [w for w in re.findall(r"[a-z0-9+#./-]+", k) if len(w) > 2]
    if len(parts) >= 2:
        return all(p in low for p in parts)
    return False


def keyword_coverage_pct(resume_text: str, keywords: list[str]) -> float:
    if not keywords:
        return 100.0
    hits = sum(1 for k in keywords if keyword_in_resume(k, resume_text))
    return 100.0 * hits / len(keywords)


def jd_alignment_pct(resume_text: str, jd_text: str) -> float:
    jd_tokens = _tokenize(jd_text)
    if not jd_tokens:
        return 50.0
    resume_tokens = _tokenize(resume_text)
    overlap = len(jd_tokens & resume_tokens) / len(jd_tokens)
    return min(100.0, overlap * 115.0)


def gap_readiness_pct(gap_count: int, *, max_gaps: int = 8) -> float:
    if gap_count <= 0:
        return 100.0
    penalty = min(gap_count / max_gaps, 1.0)
    return max(0.0, 100.0 * (1.0 - penalty))


def _label_for_score(pct: float) -> str:
    if pct >= 85:
        return "Strong match"
    if pct >= 70:
        return "Good match"
    if pct >= 55:
        return "Moderate match"
    return "Needs improvement"


def _summary_for_score(pct: float, keyword_pct: float, gap_count: int) -> str:
    if pct >= 85:
        return "Resume aligns well with this role for typical ATS screening."
    if pct >= 70:
        return "Solid ATS alignment; a few JD terms could still be strengthened."
    if pct >= 55:
        return "Partial ATS fit — tailor wording and add missing role keywords."
    if gap_count > 4 and keyword_pct < 50:
        return "Low ATS alignment — address gaps and weave in more JD keywords."
    return "Significant gaps vs the job description; customize before applying."


@dataclass
class _Weights:
    keyword: float = 0.55
    jd: float = 0.20
    gap: float = 0.25


def compute_ats_match(
    *,
    resume_text: str,
    jd_text: str,
    keywords: list[str],
    gaps: list[str] | None = None,
    keyword_hits: list[KeywordHit] | None = None,
) -> AtsMatchScore:
    gap_list = gaps or []
    kw_hits = keyword_hits
    if kw_hits is None:
        kw_hits = [
            KeywordHit(keyword=k, found_in_resume=keyword_in_resume(k, resume_text))
            for k in keywords
        ]

    kw_pct = keyword_coverage_pct(resume_text, keywords)
    jd_pct = jd_alignment_pct(resume_text, jd_text)
    gap_pct = gap_readiness_pct(len(gap_list))

    w = _Weights()
    overall = w.keyword * kw_pct + w.jd * jd_pct + w.gap * gap_pct
    overall = round(min(100.0, max(0.0, overall)), 1)

    matched = sum(1 for h in kw_hits if h.found_in_resume)
    return AtsMatchScore(
        score_pct=overall,
        keyword_coverage_pct=round(kw_pct, 1),
        jd_alignment_pct=round(jd_pct, 1),
        gap_readiness_pct=round(gap_pct, 1),
        keywords_matched=matched,
        keywords_total=len(keywords),
        gaps_count=len(gap_list),
        label=_label_for_score(overall),
        summary=_summary_for_score(overall, kw_pct, len(gap_list)),
        keyword_hits=kw_hits,
    )

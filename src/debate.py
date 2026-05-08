from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from src.clients import get_backend
from src.config import CHAIR_MODEL, CHAIR_PROVIDER, DEBATERS, DebaterConfig


@dataclass
class TurnEntry:
    debater_id: str
    round_name: str
    text: str


@dataclass
class DebateResult:
    """Full trace plus the single user-facing answer."""

    final_answer: str
    transcript: list[TurnEntry] = field(default_factory=list)
    analytics: "DebateAnalytics | None" = None


@dataclass
class DebaterAnalytics:
    debater_id: str
    provider: str
    model: str
    contribution_pct: float
    question_alignment_pct: float
    final_overlap_pct: float
    round2_length: int


@dataclass
class DebateAnalytics:
    final_confidence_pct: float
    consensus_pct: float
    chair_provider: str
    chair_model: str
    debaters: list[DebaterAnalytics]


ROUND1_SYSTEM = """You are one expert in a panel. Answer the user's question directly.
Be concise but complete. This is round 1: give your best standalone answer."""


def _round1_user(question: str, cfg: DebaterConfig) -> str:
    return f"{cfg.persona}\n\nUser question:\n{question}"


ROUND2_SYSTEM = """You are still the same panelist. Below are round-1 answers from all panelists (including yours).
Critique others where they are weak; concede where they are stronger. Then give an improved answer
that could stand alone. Stay constructive."""


def _round2_user(question: str, cfg: DebaterConfig, round1_blocks: str) -> str:
    return (
        f"{cfg.persona}\n\nUser question:\n{question}\n\n"
        f"--- Round 1 (all panelists) ---\n{round1_blocks}\n"
        f"--- End round 1 ---\n\nYour round-2 improved answer:"
    )


CHAIR_SYSTEM = """You chair a private expert panel. You see the user question and the full discussion.
Your job is to reconcile conflicting views into ONE answer the user can use.

Internal process (do not print these steps as a numbered list—use them to think, then write the answer):
1) List where panelists agree; treat that as the backbone of the answer.
2) Where they disagree, weigh: specificity to the question, internal consistency, and whether a claim is hedged vs overconfident.
3) Prefer answers that acknowledge tradeoffs when experts split; pick a default recommendation when the user needs to act.
4) If only one view is well-supported and others hand-wave, favor the well-supported view.

Output requirements:
- Output only the final answer for the user—no meta commentary about the panel, rounds, or models.
- Merge the strongest points; when you resolve a disagreement, fold the reasoning into the answer naturally (not as "some said X, others Y").
- If uncertainty remains, state it briefly and give the best default recommendation.
- Match the user's requested depth (if they asked for a short answer, keep it short)."""


def _chair_user(question: str, transcript: str) -> str:
    return f"User question:\n{question}\n\nFull panel discussion:\n{transcript}"


def _run_debater_round1(question: str, cfg: DebaterConfig) -> TurnEntry:
    backend = get_backend(cfg.provider, cfg.model)
    text = backend.complete(ROUND1_SYSTEM, _round1_user(question, cfg))
    return TurnEntry(cfg.id, "round1", text)


def _run_debater_round2(question: str, cfg: DebaterConfig, round1_blocks: str) -> TurnEntry:
    backend = get_backend(cfg.provider, cfg.model)
    text = backend.complete(ROUND2_SYSTEM, _round2_user(question, cfg, round1_blocks))
    return TurnEntry(cfg.id, "round2", text)


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def _pct(v: float) -> float:
    return round(max(0.0, min(100.0, v * 100.0)), 1)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _compute_analytics(question: str, final_answer: str, r2: list[TurnEntry]) -> DebateAnalytics:
    q_tokens = _tokenize(question)
    final_tokens = _tokenize(final_answer)

    raw_rows: list[tuple[TurnEntry, float, float, int]] = []
    for t in r2:
        ans_tokens = _tokenize(t.text)
        q_align = _jaccard(ans_tokens, q_tokens)
        f_overlap = _jaccard(ans_tokens, final_tokens)
        length = len(t.text.strip())
        # Blend overlap and relevance; tiny bonus for substantial responses (capped).
        support = (f_overlap * 0.65) + (q_align * 0.3) + min(length / 1200.0, 1.0) * 0.05
        raw_rows.append((t, support, q_align, length))

    total_support = sum(x[1] for x in raw_rows)
    debaters: list[DebaterAnalytics] = []
    for t, support, q_align, length in raw_rows:
        cfg = next((d for d in DEBATERS if d.id == t.debater_id), None)
        contrib = (support / total_support) if total_support > 0 else (1 / max(len(raw_rows), 1))
        debaters.append(
            DebaterAnalytics(
                debater_id=t.debater_id,
                provider=(cfg.provider if cfg else "unknown"),
                model=(cfg.model if cfg else "unknown"),
                contribution_pct=_pct(contrib),
                question_alignment_pct=_pct(q_align),
                final_overlap_pct=_pct(_jaccard(_tokenize(t.text), final_tokens)),
                round2_length=length,
            ),
        )

    # Average pairwise agreement among round-2 responses.
    pair_scores: list[float] = []
    for i in range(len(r2)):
        for j in range(i + 1, len(r2)):
            pair_scores.append(_jaccard(_tokenize(r2[i].text), _tokenize(r2[j].text)))
    consensus = (sum(pair_scores) / len(pair_scores)) if pair_scores else 0.0

    mean_align = (
        sum(d.question_alignment_pct for d in debaters) / (100.0 * len(debaters))
        if debaters
        else 0.0
    )
    mean_overlap = (
        sum(d.final_overlap_pct for d in debaters) / (100.0 * len(debaters)) if debaters else 0.0
    )
    final_confidence = (consensus * 0.4) + (mean_align * 0.35) + (mean_overlap * 0.25)

    return DebateAnalytics(
        final_confidence_pct=_pct(final_confidence),
        consensus_pct=_pct(consensus),
        chair_provider=CHAIR_PROVIDER,
        chair_model=CHAIR_MODEL,
        debaters=debaters,
    )


def run_debate(question: str) -> DebateResult:
    transcript: list[TurnEntry] = []

    with ThreadPoolExecutor(max_workers=len(DEBATERS)) as ex:
        futs = {ex.submit(_run_debater_round1, question, c): c for c in DEBATERS}
        r1: list[TurnEntry] = []
        for fut in as_completed(futs):
            r1.append(fut.result())
    r1.sort(key=lambda t: next(i for i, c in enumerate(DEBATERS) if c.id == t.debater_id))
    transcript.extend(r1)

    round1_blocks = "\n\n".join(
        f"[{t.debater_id}]\n{t.text}" for t in r1
    )

    with ThreadPoolExecutor(max_workers=len(DEBATERS)) as ex:
        futs = {ex.submit(_run_debater_round2, question, c, round1_blocks): c for c in DEBATERS}
        r2: list[TurnEntry] = []
        for fut in as_completed(futs):
            r2.append(fut.result())
    r2.sort(key=lambda t: next(i for i, c in enumerate(DEBATERS) if c.id == t.debater_id))
    transcript.extend(r2)

    full_text = "\n\n".join(
        f"### {t.round_name} / {t.debater_id}\n{t.text}" for t in transcript
    )

    chair = get_backend(CHAIR_PROVIDER, CHAIR_MODEL)
    final = chair.complete(CHAIR_SYSTEM, _chair_user(question, full_text))
    final_clean = final.strip()
    analytics = _compute_analytics(question, final_clean, r2)
    return DebateResult(final_answer=final_clean, transcript=transcript, analytics=analytics)

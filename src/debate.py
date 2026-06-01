from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from src.clients import get_backend
from src.config import CHAIR_MODEL, CHAIR_PROVIDER, DEBATERS, DebaterConfig
from src.resume.format import sanitize_panel_turn

StageCallback = Callable[[str, str], None]


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
    display_name: str
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
Be concise but complete. This is round 1: give your best standalone answer.

Quality bar:
- Be accurate and specific.
- State assumptions briefly if needed.
- Prefer concrete recommendations over generic advice."""


def _round1_user(task: str, cfg: DebaterConfig) -> str:
    return f"{cfg.persona}\n\nUser task:\n{task}"


ROUND2_SYSTEM = """You are still the same panelist. Below are round-1 answers from all panelists (including yours).
Critique others where they are weak; concede where they are stronger. Then give an improved answer
that could stand alone. Stay constructive.

Output format:
1) "What I changed" (2-4 bullets)
2) "Improved answer" (final standalone answer)"""


def _round2_user(task: str, cfg: DebaterConfig, round1_blocks: str) -> str:
    return (
        f"{cfg.persona}\n\nUser task:\n{task}\n\n"
        f"--- Round 1 (all panelists) ---\n{round1_blocks}\n"
        f"--- End round 1 ---\n\nYour round-2 improved answer:"
    )


CHAIR_SYSTEM = """You chair a private expert panel. You see the user question and the full discussion.
Your job is to reconcile conflicting views into ONE answer the user can use.

Internal process (do not print these steps):
1) Identify strongest claims from each panelist.
2) Build the final answer by selecting the best parts across panelists (do not average weak and strong points).
3) Resolve conflicts by choosing the most specific, consistent, and actionable claim.
4) Keep only high-signal content; remove redundancy and fluff.

Output requirements:
- Output only the final answer for the user (no meta commentary about panel/models/rounds).
- The final answer should clearly reflect best contributions from multiple panelists when useful.
- If uncertainty remains, state it briefly and provide the best default action.
- Match requested depth.
- Use this output format exactly:
  ## Final recommendation
  <1 concise paragraph>
  ## Why this is best
  - <2-4 bullet points>
  ## Action steps
  1. <step>
  2. <step>
  3. <step>"""


def _chair_user(task: str, transcript: str) -> str:
    return f"User task:\n{task}\n\nFull panel discussion:\n{transcript}"


def _normalize_final_answer_format(text: str) -> str:
    s = text.replace("\r\n", "\n").strip()
    # Ensure section headings start on fresh lines and have breathing room.
    s = re.sub(r"\n{0,2}(##\s+)", r"\n\n\1", s)
    # Keep numbered/bulleted list spacing readable.
    s = re.sub(r"\n{3,}", "\n\n", s)
    # Ensure bullet and numbered list markers are separated from prior paragraph.
    s = re.sub(r"([^\n])\n([-*]\s+)", r"\1\n\n\2", s)
    s = re.sub(r"([^\n])\n(\d+\.\s+)", r"\1\n\n\2", s)
    return s.strip()


def _normalize_resume_markdown(text: str) -> str:
    s = text.replace("\r\n", "\n").strip()
    s = re.sub(r"^```(?:markdown)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


@dataclass(frozen=True)
class FusionPrompts:
    round1_system: str
    round2_system: str
    chair_system: str
    postprocess: Callable[[str], str] = _normalize_final_answer_format
    sanitize_turn: Callable[[str], str] | None = None


DEFAULT_FUSION_PROMPTS = FusionPrompts(
    round1_system=ROUND1_SYSTEM,
    round2_system=ROUND2_SYSTEM,
    chair_system=CHAIR_SYSTEM,
)

RESUME_FUSION_PROMPTS = FusionPrompts(
    round1_system="""You are one expert resume editor in a panel. Tailor the candidate's resume copy for the job.
Preserve the SOURCE resume's exact structure: same section headings (verbatim), section order, bullet markers,
table rows, blank lines, line breaks, and spacing. Improve wording and JD alignment only where truthful.
Do not invent employers, degrees, titles, or dates. No AI-style headings. Write like a human resume.

CRITICAL: Output ONLY the resume text. No commentary, planning, line counts, or meta notes.""",
    round2_system="""You are still the same resume-editing panelist. Review round-1 drafts from all panelists.
Improve weak bullets; adopt stronger phrasing from peers where accurate. Keep the source format unchanged.

CRITICAL: Output ONLY the full improved resume text. Do NOT include "What I changed", reasoning, line counts,
or any commentary — resume content only.""",
    chair_system="""You chair a private panel of resume editors. Output ONE final resume for the candidate.

Rules:
- Output ONLY the final resume text — nothing else.
- NEVER include reasoning, planning, line counts, "What I changed", or notes about the panel/task.
- Preserve source section headings verbatim, section order, bullet characters, blank lines, and spacing.
- Do not rename sections or add decorative/AI headings.
- Do not fabricate employers, degrees, titles, or dates.
- Weave JD keywords naturally where accurate.""",
    postprocess=_normalize_resume_markdown,
    sanitize_turn=sanitize_panel_turn,
)


def _run_debater_round1(task: str, cfg: DebaterConfig, prompts: FusionPrompts) -> TurnEntry:
    backend = get_backend(cfg.provider, cfg.model)
    text = backend.complete(prompts.round1_system, _round1_user(task, cfg))
    return TurnEntry(cfg.id, "round1", text)


def _run_debater_round2(
    task: str,
    cfg: DebaterConfig,
    round1_blocks: str,
    prompts: FusionPrompts,
) -> TurnEntry:
    backend = get_backend(cfg.provider, cfg.model)
    text = backend.complete(prompts.round2_system, _round2_user(task, cfg, round1_blocks))
    return TurnEntry(cfg.id, "round2", text)


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}

def _char_ngrams(text: str, n: int = 4) -> set[str]:
    # Use character n-grams to make the metric more tolerant to synonyms/rewrites.
    s = re.sub(r"\s+", " ", text.lower().strip())
    if len(s) < n:
        return set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def _provider_label(provider: str) -> str:
    p = provider.lower().strip()
    if p == "openai":
        return "OpenAI"
    if p == "anthropic":
        return "Anthropic"
    if p == "bedrock":
        return "Bedrock"
    return provider


def _pct(v: float) -> float:
    return round(max(0.0, min(100.0, v * 100.0)), 1)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def _containment(a: set[str], b: set[str]) -> float:
    """How much of `b` is covered by `a` (useful for question alignment)."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(b)


def _compute_analytics(question: str, final_answer: str, r2: list[TurnEntry]) -> DebateAnalytics:
    q_tokens = _tokenize(question)
    final_tokens = _tokenize(final_answer)
    q_chars = _char_ngrams(question)
    final_chars = _char_ngrams(final_answer)

    raw_rows: list[tuple[TurnEntry, float, float, int]] = []
    for t in r2:
        ans_tokens = _tokenize(t.text)
        ans_chars = _char_ngrams(t.text)

        # Question alignment: token containment + character overlap.
        q_token_cov = _containment(ans_tokens, q_tokens)  # coverage of question
        q_char_sim = _jaccard(ans_chars, q_chars)  # tolerance to paraphrases
        q_align = (0.6 * q_token_cov) + (0.4 * q_char_sim)

        # Final overlap: how much of the final answer is reflected in the model response.
        f_token_cov = _containment(ans_tokens, final_tokens)
        f_char_sim = _jaccard(ans_chars, final_chars)
        f_overlap = (0.6 * f_token_cov) + (0.4 * f_char_sim)

        length = len(t.text.strip())
        # Blend overlap and relevance; small bonus for substantial responses (capped).
        support = (f_overlap * 0.7) + (q_align * 0.25) + min(length / 1200.0, 1.0) * 0.05
        raw_rows.append((t, support, q_align, length))

    total_support = sum(x[1] for x in raw_rows)
    debaters: list[DebaterAnalytics] = []
    for t, support, q_align, length in raw_rows:
        cfg = next((d for d in DEBATERS if d.id == t.debater_id), None)
        contrib = (support / total_support) if total_support > 0 else (1 / max(len(raw_rows), 1))
        debaters.append(
            DebaterAnalytics(
                debater_id=t.debater_id,
                display_name=(
                    f"{_provider_label(cfg.provider)} - {cfg.model}" if cfg else t.debater_id
                ),
                provider=(cfg.provider if cfg else "unknown"),
                model=(cfg.model if cfg else "unknown"),
                contribution_pct=_pct(contrib),
                question_alignment_pct=_pct(q_align),
                final_overlap_pct=_pct(_jaccard(_tokenize(t.text), final_tokens)),
                round2_length=length,
            ),
        )

    # Average pairwise agreement among round-2 responses (token coverage + char similarity).
    pair_scores: list[float] = []
    for i in range(len(r2)):
        for j in range(i + 1, len(r2)):
            a_tok = _tokenize(r2[i].text)
            b_tok = _tokenize(r2[j].text)
            a_chars = _char_ngrams(r2[i].text)
            b_chars = _char_ngrams(r2[j].text)

            tok_agree = 0.5 * (_containment(a_tok, b_tok) + _containment(b_tok, a_tok))
            char_agree = _jaccard(a_chars, b_chars)
            pair_scores.append((0.65 * tok_agree) + (0.35 * char_agree))
    consensus = (sum(pair_scores) / len(pair_scores)) if pair_scores else 0.0

    mean_align = (
        sum(d.question_alignment_pct for d in debaters) / (100.0 * len(debaters))
        if debaters
        else 0.0
    )
    mean_overlap = (
        sum(d.final_overlap_pct for d in debaters) / (100.0 * len(debaters)) if debaters else 0.0
    )
    raw_confidence = (consensus * 0.3) + (mean_align * 0.45) + (mean_overlap * 0.25)
    # Calibrate for display: overlap-based metrics can be sparse for good answers due to paraphrases.
    # So we map raw confidence into a higher baseline without hiding low-quality runs.
    final_confidence = min(1.0, 0.25 + (raw_confidence * 0.9))

    return DebateAnalytics(
        final_confidence_pct=_pct(final_confidence),
        consensus_pct=_pct(consensus),
        chair_provider=CHAIR_PROVIDER,
        chair_model=CHAIR_MODEL,
        debaters=debaters,
    )


def run_fusion(
    task: str,
    prompts: FusionPrompts = DEFAULT_FUSION_PROMPTS,
    on_stage: StageCallback | None = None,
) -> DebateResult:
    transcript: list[TurnEntry] = []

    if on_stage:
        on_stage("fusion_round1", "Panel drafting initial responses…")

    with ThreadPoolExecutor(max_workers=len(DEBATERS)) as ex:
        futs = {ex.submit(_run_debater_round1, task, c, prompts): c for c in DEBATERS}
        r1: list[TurnEntry] = []
        for fut in as_completed(futs):
            r1.append(fut.result())
    r1.sort(key=lambda t: next(i for i, c in enumerate(DEBATERS) if c.id == t.debater_id))
    transcript.extend(r1)

    round1_blocks = "\n\n".join(f"[{t.debater_id}]\n{t.text}" for t in r1)

    if on_stage:
        on_stage("fusion_round2", "Crossfire pass: models challenge and refine drafts…")

    with ThreadPoolExecutor(max_workers=len(DEBATERS)) as ex:
        futs = {
            ex.submit(_run_debater_round2, task, c, round1_blocks, prompts): c for c in DEBATERS
        }
        r2: list[TurnEntry] = []
        for fut in as_completed(futs):
            r2.append(fut.result())
    r2.sort(key=lambda t: next(i for i, c in enumerate(DEBATERS) if c.id == t.debater_id))
    transcript.extend(r2)

    full_text = "\n\n".join(
        f"### {t.round_name} / {t.debater_id}\n"
        f"{prompts.sanitize_turn(t.text) if prompts.sanitize_turn else t.text}"
        for t in transcript
    )

    if on_stage:
        on_stage("fusion_chair", "Chair synthesizing one final output…")

    chair = get_backend(CHAIR_PROVIDER, CHAIR_MODEL)
    final = chair.complete(prompts.chair_system, _chair_user(task, full_text))
    final_clean = prompts.postprocess(final)
    if prompts.sanitize_turn:
        final_clean = prompts.sanitize_turn(final_clean)
    analytics = _compute_analytics(task, final_clean, r2)
    return DebateResult(final_answer=final_clean, transcript=transcript, analytics=analytics)


def run_debate(question: str) -> DebateResult:
    return run_fusion(question, DEFAULT_FUSION_PROMPTS)

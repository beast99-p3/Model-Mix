import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { formatFastApiError } from "../lib/apiError";

type TranscriptEntry = {
  debater_id: string;
  round_name: string;
  text: string;
};

type DebaterScore = {
  debater_id: string;
  display_name: string;
  provider: string;
  model: string;
  contribution_pct: number;
  question_alignment_pct: number;
  final_overlap_pct: number;
  round2_length: number;
};

type DebateAnalytics = {
  final_confidence_pct: number;
  consensus_pct: number;
  chair_provider: string;
  chair_model: string;
  debaters: DebaterScore[];
};

type DebateResponse = {
  final_answer: string;
  transcript?: TranscriptEntry[];
  analytics?: DebateAnalytics;
};

const WAIT_LINES = [
  "Signal drafting: each intelligence sketches a strategy",
  "Crossfire pass: contenders challenge and strengthen claims",
  "Fusion pass: chair weaves the strongest pieces together",
];

const WAIT_NODES = ["Anthropic", "OpenAI", "Gemma", "DeepSeek"];

function clampPct(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(100, v));
}

export function DebateMode() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DebateResponse | null>(null);
  const [showTranscript, setShowTranscript] = useState(true);
  const [lineIdx, setLineIdx] = useState(0);

  useEffect(() => {
    if (!loading) return;
    const t = window.setInterval(() => {
      setLineIdx((i) => (i + 1) % WAIT_LINES.length);
    }, 2200);
    return () => window.clearInterval(t);
  }, [loading]);

  const scores = useMemo(() => {
    const rows = result?.analytics?.debaters ?? [];
    return [...rows].sort((a, b) => b.contribution_pct - a.contribution_pct);
  }, [result]);

  async function runDebate() {
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setLineIdx(0);

    try {
      const res = await fetch("/api/debate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, show_transcript: showTranscript }),
      });
      const body = (await res.json().catch(() => null)) as DebateResponse | null;
      if (!res.ok) {
        setError(formatFastApiError(body, res.statusText));
        return;
      }
      setResult(body);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-white">Fusion mode</h1>
        <p className="mt-1 text-sm text-slate-400">
          Models debate privately, then a chair returns one answer with contribution scores.
        </p>
      </div>

      <div className="rounded-xl border border-white/10 bg-surface p-4 shadow-xl">
        <label htmlFor="debate-question" className="mb-2 block text-sm text-slate-300">
          Ask your question
        </label>
        <textarea
          id="debate-question"
          className="min-h-[120px] w-full resize-y rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none focus:border-accent/50"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Example: Build a tailored answer for this JD and explain why each keyword matters."
        />
        <label className="mt-3 flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={showTranscript}
            onChange={(e) => setShowTranscript(e.target.checked)}
          />
          Include debate transcript
        </label>
        <button
          type="button"
          onClick={() => void runDebate()}
          disabled={loading || !question.trim()}
          className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-emerald-950 disabled:opacity-50"
        >
          {loading ? "Debating..." : "Run debate"}
        </button>
      </div>

      {loading && (
        <div className="rounded-xl border border-white/10 bg-surface p-5 shadow-xl">
          <div className="relative mx-auto mb-5 grid h-56 w-full max-w-xl place-items-center overflow-hidden rounded-xl border border-white/10 bg-black/20">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(110,231,183,0.22),transparent_60%)]" />
            <div className="absolute h-24 w-24 animate-ping rounded-full border border-accent/30 bg-accent/5" />
            <div className="absolute text-xs font-semibold tracking-wide text-accent">FUSION CORE</div>
            <div className="absolute h-[2px] w-[75%] animate-pulse bg-gradient-to-r from-transparent via-accent/50 to-transparent" />
            <div className="absolute h-[2px] w-[75%] -rotate-12 animate-pulse bg-gradient-to-r from-transparent via-cyan-300/40 to-transparent" />
            <div className="absolute h-[2px] w-[75%] rotate-12 animate-pulse bg-gradient-to-r from-transparent via-emerald-300/40 to-transparent" />
            {WAIT_NODES.map((name, i) => (
              <div
                key={name}
                className="absolute grid h-16 w-16 place-items-center rounded-full border border-white/20 bg-[#111827]/90 px-1 text-center text-[10px] font-semibold text-slate-200 shadow-[0_0_24px_rgba(110,231,183,0.22)]"
                style={{
                  transform: `translate(${Math.cos((Math.PI * 2 * i) / WAIT_NODES.length + lineIdx * 0.45) * 130}px, ${Math.sin((Math.PI * 2 * i) / WAIT_NODES.length + lineIdx * 0.45) * 68}px)`,
                  transition: "transform 900ms ease",
                }}
              >
                {name}
              </div>
            ))}
          </div>
          <p className="text-center text-sm font-semibold text-white">Synthesizing best answer...</p>
          <p className="mt-1 text-center text-sm text-slate-400">{WAIT_LINES[lineIdx]}</p>
          <div className="mt-4 overflow-hidden rounded-full border border-white/10 bg-black/20">
            <div className="h-2 w-full animate-pulse bg-accent/60" />
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="rounded-xl border border-white/10 bg-surface p-4 shadow-xl">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Final answer
            </h2>
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown>{result.final_answer || ""}</ReactMarkdown>
            </div>
          </div>

          {result.analytics && (
            <div className="rounded-xl border border-white/10 bg-surface p-4 shadow-xl">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                Quality and contribution
              </h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                  <p className="text-xs text-slate-400">Final confidence</p>
                  <p className="text-2xl font-semibold text-white">
                    {clampPct(result.analytics.final_confidence_pct).toFixed(1)}%
                  </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                  <p className="text-xs text-slate-400">Panel consensus</p>
                  <p className="text-2xl font-semibold text-white">
                    {clampPct(result.analytics.consensus_pct).toFixed(1)}%
                  </p>
                </div>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                Final confidence blends relevance, agreement, and how much of each model's content survives in
                the final merged answer.
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Panel consensus measures average agreement between model responses before chair synthesis.
              </p>
              <p className="mt-3 text-xs text-slate-500">
                Chair model: {result.analytics.chair_provider} / {result.analytics.chair_model}
              </p>

              <div className="mt-4 space-y-3">
                {scores.map((s) => (
                  <div key={`${s.debater_id}-${s.model}`} className="rounded-lg border border-white/10 p-3">
                    <div className="mb-1 flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-white">{s.display_name}</p>
                      <p className="text-sm text-accent">{clampPct(s.contribution_pct).toFixed(1)}%</p>
                    </div>
                    <div className="h-2 rounded-full bg-black/30">
                      <div
                        className="h-2 rounded-full bg-accent"
                        style={{ width: `${clampPct(s.contribution_pct)}%` }}
                      />
                    </div>
                    <p className="mt-2 text-xs text-slate-400">
                      Alignment: {clampPct(s.question_alignment_pct).toFixed(1)}% | Final overlap:{" "}
                      {clampPct(s.final_overlap_pct).toFixed(1)}% | Provider: {s.provider}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {showTranscript && Array.isArray(result.transcript) && result.transcript.length > 0 && (
            <details className="rounded-xl border border-white/10 bg-surface p-4 shadow-xl">
              <summary className="cursor-pointer text-sm font-semibold text-slate-300">
                Debate transcript
              </summary>
              <div className="mt-3 space-y-3">
                {result.transcript.map((t, idx) => (
                  <div key={`${t.round_name}-${t.debater_id}-${idx}`} className="rounded-lg border border-white/10 p-3">
                    <p className="mb-1 text-xs font-mono text-accent">
                      {t.round_name} / {scores.find((s) => s.debater_id === t.debater_id)?.display_name ?? t.debater_id}
                    </p>
                    <p className="whitespace-pre-wrap text-sm text-slate-300">{t.text}</p>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

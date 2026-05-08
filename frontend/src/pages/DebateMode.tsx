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
          <div className="relative mx-auto mb-5 h-56 w-full max-w-xl overflow-hidden rounded-xl border border-white/10 bg-black/20">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(110,231,183,0.18),transparent_60%)]" />
            <div className="absolute inset-0 bg-[conic-gradient(from_90deg_at_center,rgba(110,231,183,0.35),rgba(56,189,248,0.18),rgba(110,231,183,0.35))] opacity-20 animate-[mmSpin_6s_linear_infinite]" />

            <div className="absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2">
              <div className="absolute inset-0 animate-[mmSpin_4s_linear_infinite] rounded-full" style={{ background: "conic-gradient(from 0deg, rgba(110,231,183,0.0), rgba(110,231,183,0.7), rgba(56,189,248,0.35), rgba(110,231,183,0.0))" }} />
              <div className="absolute inset-6 rounded-full bg-black/35 border border-white/10" />
              <div className="absolute inset-0 rounded-full border border-white/10 opacity-50" style={{ boxShadow: "0 0 60px rgba(110,231,183,0.12)" }} />
            </div>

            <div className="absolute bottom-6 left-7 right-7 space-y-3">
              {[0, 1, 2].map((idx) => (
                <div key={idx} className="h-3 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full w-[55%] rounded-full bg-gradient-to-r from-transparent via-accent/70 to-transparent"
                    style={{
                      transform: `translateX(${idx === 1 ? -10 : 0}%)`,
                      animation: `mmEnergy_1.6s_ease-in-out_infinite`,
                      animationDelay: `${idx * 160}ms`,
                    }}
                  />
                </div>
              ))}
            </div>

            <div className="absolute left-6 top-5 text-[11px] font-semibold tracking-widest text-accent">
              FUSION ENGINE
            </div>

            <style>{`
              @keyframes mmSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
              @keyframes mmEnergy {
                0% { transform: translateX(-120%); opacity: 0.25; }
                35% { opacity: 0.9; }
                100% { transform: translateX(260%); opacity: 0.15; }
              }
            `}</style>
          </div>
          <p className="text-center text-sm font-semibold text-white">Synthesizing best answer...</p>
          <p className="mt-1 text-center text-sm text-slate-400">{WAIT_LINES[lineIdx]}</p>
          <div className="mt-4 overflow-hidden rounded-full border border-white/10 bg-black/20">
            <div
              className="h-2 bg-gradient-to-r from-cyan-300 via-accent to-emerald-300 transition-all duration-700"
              style={{ width: `${Math.min(95, 30 + lineIdx * 22)}%` }}
            />
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
            <div className="prose prose-invert prose-sm max-w-none leading-7 prose-headings:mb-2 prose-headings:mt-5 prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-1">
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
                Final confidence is a heuristic. It blends question alignment, panel consensus, and how much the
                models agree with each other before the chair merges them. A calibration step keeps good fusion runs
                from looking artificially low due to paraphrasing.
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

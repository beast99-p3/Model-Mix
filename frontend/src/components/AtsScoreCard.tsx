export type AtsMatch = {
  score_pct: number;
  keyword_coverage_pct: number;
  jd_alignment_pct: number;
  gap_readiness_pct: number;
  keywords_matched: number;
  keywords_total: number;
  gaps_count: number;
  label: string;
  summary: string;
};

function scoreColor(pct: number): string {
  if (pct >= 85) return "text-emerald-400";
  if (pct >= 70) return "text-accent";
  if (pct >= 55) return "text-amber-300";
  return "text-orange-300";
}

function ringColor(pct: number): string {
  if (pct >= 85) return "stroke-emerald-400";
  if (pct >= 70) return "stroke-accent";
  if (pct >= 55) return "stroke-amber-400";
  return "stroke-orange-400";
}

type Props = {
  match: AtsMatch;
  title?: string;
  baselinePct?: number | null;
  compact?: boolean;
};

export function AtsScoreCard({ match, title = "ATS match", baselinePct = null, compact = false }: Props) {
  const pct = Math.round(match.score_pct);
  const delta =
    baselinePct != null && baselinePct !== pct ? Math.round(pct - baselinePct) : null;
  const circumference = 2 * Math.PI * 42;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div
      className={`rounded-xl border border-white/10 bg-black/25 ${
        compact ? "p-4" : "p-5"
      }`}
    >
      <div className="flex flex-wrap items-start gap-5">
        <div className="relative h-24 w-24 shrink-0">
          <svg className="h-24 w-24 -rotate-90" viewBox="0 0 100 100" aria-hidden>
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              className="stroke-white/10"
              strokeWidth="8"
            />
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              className={ringColor(pct)}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-2xl font-bold tabular-nums ${scoreColor(pct)}`}>{pct}%</span>
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h3>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                pct >= 70 ? "bg-emerald-500/15 text-emerald-200" : "bg-amber-500/15 text-amber-100"
              }`}
            >
              {match.label}
            </span>
            {delta !== null && delta !== 0 && (
              <span
                className={`text-xs font-semibold tabular-nums ${
                  delta > 0 ? "text-emerald-400" : "text-amber-300"
                }`}
              >
                {delta > 0 ? "+" : ""}
                {delta}% vs original
              </span>
            )}
          </div>
          <p className="mt-2 text-sm text-slate-300">{match.summary}</p>
          {!compact && (
            <dl className="mt-4 grid grid-cols-3 gap-3 text-center">
              <div className="rounded-lg bg-white/5 px-2 py-2">
                <dt className="text-[10px] uppercase text-slate-500">Keywords</dt>
                <dd className="text-sm font-semibold text-white tabular-nums">
                  {Math.round(match.keyword_coverage_pct)}%
                </dd>
                <dd className="text-[10px] text-slate-500">
                  {match.keywords_matched}/{match.keywords_total}
                </dd>
              </div>
              <div className="rounded-lg bg-white/5 px-2 py-2">
                <dt className="text-[10px] uppercase text-slate-500">JD terms</dt>
                <dd className="text-sm font-semibold text-white tabular-nums">
                  {Math.round(match.jd_alignment_pct)}%
                </dd>
              </div>
              <div className="rounded-lg bg-white/5 px-2 py-2">
                <dt className="text-[10px] uppercase text-slate-500">Gap readiness</dt>
                <dd className="text-sm font-semibold text-white tabular-nums">
                  {Math.round(match.gap_readiness_pct)}%
                </dd>
                {match.gaps_count > 0 && (
                  <dd className="text-[10px] text-slate-500">{match.gaps_count} gaps noted</dd>
                )}
              </div>
            </dl>
          )}
        </div>
      </div>
    </div>
  );
}

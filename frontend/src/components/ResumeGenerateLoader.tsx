type Props = {
  statusLine: string;
  progress: number;
};

export function ResumeGenerateLoader({ statusLine, progress }: Props) {
  const pct = Math.min(95, progress);

  return (
    <div className="rounded-xl border border-white/10 bg-surface p-5 shadow-xl">
      <div className="relative mx-auto mb-4 h-48 w-full max-w-lg overflow-hidden rounded-xl border border-white/10 bg-[#080c12]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_50%,rgba(110,231,183,0.1),transparent_55%)]" />

        <div className="absolute inset-0 flex items-center justify-center gap-3 px-8">
          {["A", "Q", "N", "L"].map((label, i) => (
            <div key={label} className="flex flex-col items-center gap-2">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-accent/30 bg-accent/10 text-xs font-bold text-accent animate-[rgPulse_1.6s_ease-in-out_infinite]"
                style={{ animationDelay: `${i * 0.25}s` }}
              >
                {label}
              </div>
              <div className="h-8 w-px bg-gradient-to-b from-accent/50 to-transparent animate-[rgPulse_1.6s_ease-in-out_infinite]" style={{ animationDelay: `${i * 0.25}s` }} />
            </div>
          ))}
        </div>

        <div className="absolute bottom-5 left-1/2 h-12 w-40 -translate-x-1/2 rounded-lg border border-accent/40 bg-black/50">
          <div className="flex h-full items-center justify-center text-[10px] font-semibold tracking-[0.18em] text-accent">
            CHAIR MERGE
          </div>
          <div className="absolute inset-x-2 bottom-1 h-1 overflow-hidden rounded-full bg-white/10">
            <div className="h-full w-1/2 animate-[rgBar_1.2s_ease-in-out_infinite] rounded-full bg-accent/70" />
          </div>
        </div>

        <div className="absolute left-4 top-4 text-[10px] font-semibold tracking-[0.2em] text-accent/90">
          FUSION DRAFT
        </div>
      </div>

      <p className="text-center text-sm font-semibold text-white">Generating tailored resume…</p>
      <p className="mt-1 text-center text-sm text-slate-400">{statusLine}</p>
      <div className="mt-4 overflow-hidden rounded-full border border-white/10 bg-black/20">
        <div
          className="h-2 rounded-full bg-gradient-to-r from-emerald-400 via-accent to-cyan-300 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <style>{`
        @keyframes rgPulse {
          0%, 100% { opacity: 0.45; transform: scale(0.94); }
          50% { opacity: 1; transform: scale(1); }
        }
        @keyframes rgBar {
          0% { transform: translateX(-120%); }
          100% { transform: translateX(260%); }
        }
      `}</style>
    </div>
  );
}

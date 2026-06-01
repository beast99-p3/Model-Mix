const STEPS = [
  "Extracting resume text and layout…",
  "Scanning job description keywords…",
  "Finding gaps vs. your resume…",
];

type Props = {
  phase: number;
};

export function ResumeAnalyzeLoader({ phase }: Props) {
  const progress = Math.min(92, 18 + phase * 24);

  return (
    <div className="rounded-xl border border-white/10 bg-surface p-5 shadow-xl">
      <div className="relative mx-auto mb-4 h-52 w-full max-w-lg overflow-hidden rounded-xl border border-white/10 bg-[#080c12]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_40%,rgba(56,189,248,0.12),transparent_60%)]" />

        {/* document stack */}
        <div className="absolute left-1/2 top-1/2 h-36 w-28 -translate-x-1/2 -translate-y-1/2">
          <div className="absolute inset-0 translate-x-2 translate-y-2 rounded-md border border-white/5 bg-white/[0.03]" />
          <div className="absolute inset-0 translate-x-1 translate-y-1 rounded-md border border-white/8 bg-white/[0.05]" />
          <div className="relative h-full w-full overflow-hidden rounded-md border border-white/15 bg-black/40">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="mx-3 mt-3 h-2 rounded-full bg-white/10"
                style={{ width: `${55 + (i % 3) * 12}%` }}
              />
            ))}
            <div className="absolute inset-x-0 top-0 h-full animate-[raScan_2.2s_ease-in-out_infinite] bg-gradient-to-b from-cyan-400/0 via-cyan-400/25 to-cyan-400/0" />
          </div>
        </div>

        {/* floating keyword chips */}
        {["ATS", "JD", "GAP"].map((label, i) => (
          <div
            key={label}
            className="absolute rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-cyan-200 animate-[raFloat_2.4s_ease-in-out_infinite]"
            style={{
              left: `${14 + i * 28}%`,
              top: `${22 + (i % 2) * 8}%`,
              animationDelay: `${i * 0.4}s`,
            }}
          >
            {label}
          </div>
        ))}

        <div className="absolute bottom-4 left-4 text-[10px] font-semibold tracking-[0.2em] text-cyan-300/90">
          RESUME SCAN
        </div>
      </div>

      <p className="text-center text-sm font-semibold text-white">Analyzing alignment…</p>
      <p className="mt-1 text-center text-sm text-slate-400">{STEPS[phase % STEPS.length]}</p>
      <div className="mt-4 overflow-hidden rounded-full border border-white/10 bg-black/20">
        <div
          className="h-2 rounded-full bg-gradient-to-r from-cyan-400 via-sky-300 to-cyan-200 transition-all duration-700"
          style={{ width: `${progress}%` }}
        />
      </div>

      <style>{`
        @keyframes raScan {
          0%, 100% { transform: translateY(-110%); opacity: 0.2; }
          45% { opacity: 1; }
          100% { transform: translateY(110%); opacity: 0.15; }
        }
        @keyframes raFloat {
          0%, 100% { transform: translateY(0); opacity: 0.5; }
          50% { transform: translateY(-6px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

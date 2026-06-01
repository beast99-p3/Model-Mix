const DEBATER_NODES = [
  { label: "A", color: "#6ee7b7", delay: "0s" },
  { label: "Q", color: "#38bdf8", delay: "-1.5s" },
  { label: "N", color: "#a78bfa", delay: "-3s" },
  { label: "L", color: "#f472b6", delay: "-4.5s" },
];

type Props = {
  statusLine: string;
  phase: number;
};

export function DebateFusionLoader({ statusLine, phase }: Props) {
  const progress = Math.min(95, 28 + phase * 22);

  return (
    <div className="rounded-xl border border-white/10 bg-surface p-5 shadow-xl">
      <div className="relative mx-auto mb-5 h-64 w-full max-w-xl overflow-hidden rounded-xl border border-white/10 bg-[#070a10]">
        {/* ambient glow */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_45%,rgba(110,231,183,0.14),transparent_55%)]" />
        <div className="pointer-events-none absolute inset-0 opacity-30 mix-blend-screen">
          <div className="absolute -left-1/4 top-0 h-full w-1/2 animate-[mmSweep_4s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent" />
        </div>

        {/* grid */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(110,231,183,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(110,231,183,0.5) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />

        {/* orbit rings */}
        <div className="absolute left-1/2 top-1/2 h-44 w-44 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/[0.06]" />
        <div className="absolute left-1/2 top-1/2 h-32 w-32 -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-accent/20 animate-[mmSpin_18s_linear_infinite_reverse]" />
        <div className="absolute left-1/2 top-1/2 h-56 w-56 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/[0.04] animate-[mmSpin_24s_linear_infinite]" />

        {/* orbiting debater nodes */}
        <div className="absolute left-1/2 top-1/2 h-44 w-44 -translate-x-1/2 -translate-y-1/2 animate-[mmSpin_6s_linear_infinite]">
          {DEBATER_NODES.map((node, i) => {
            const angle = (i / DEBATER_NODES.length) * 360;
            return (
              <div
                key={node.label}
                className="absolute left-1/2 top-1/2 h-9 w-9 -translate-x-1/2 -translate-y-1/2"
                style={{ transform: `rotate(${angle}deg) translateY(-88px)` }}
              >
                <div
                  className="flex h-9 w-9 animate-[mmSpin_6s_linear_infinite_reverse] items-center justify-center rounded-full border text-[11px] font-bold shadow-lg"
                  style={{
                    borderColor: `${node.color}55`,
                    background: `radial-gradient(circle at 30% 30%, ${node.color}44, rgba(0,0,0,0.65))`,
                    color: node.color,
                    boxShadow: `0 0 18px ${node.color}33`,
                    animationDelay: node.delay,
                  }}
                >
                  {node.label}
                </div>
                <div
                  className="absolute left-1/2 top-1/2 h-px w-16 origin-left -translate-y-1/2 animate-[mmBeam_1.8s_ease-in-out_infinite]"
                  style={{
                    background: `linear-gradient(90deg, ${node.color}88, transparent)`,
                    animationDelay: node.delay,
                  }}
                />
              </div>
            );
          })}
        </div>

        {/* fusion core */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="relative h-20 w-20">
            <div className="absolute inset-0 animate-[mmPulse_2s_ease-in-out_infinite] rounded-full bg-accent/20 blur-md" />
            <div className="absolute inset-2 animate-[mmSpin_3s_linear_infinite] rounded-full" style={{ background: "conic-gradient(from 0deg, rgba(110,231,183,0), rgba(110,231,183,0.85), rgba(56,189,248,0.5), rgba(110,231,183,0))" }} />
            <div className="absolute inset-4 flex items-center justify-center rounded-full border border-white/15 bg-black/50 backdrop-blur-sm">
              <span className="text-[10px] font-semibold tracking-[0.2em] text-accent">FUSE</span>
            </div>
          </div>
        </div>

        {/* data streams */}
        <div className="absolute bottom-5 left-5 right-5 space-y-2">
          {[0, 1, 2].map((idx) => (
            <div key={idx} className="relative h-2 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                className="absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-accent/80 to-transparent"
                style={{
                  animation: "mmStream 1.4s ease-in-out infinite",
                  animationDelay: `${idx * 180}ms`,
                }}
              />
            </div>
          ))}
        </div>

        {/* floating particles */}
        {[...Array(8)].map((_, i) => (
          <div
            key={i}
            className="absolute h-1 w-1 rounded-full bg-accent/60 animate-[mmFloat_3s_ease-in-out_infinite]"
            style={{
              left: `${12 + i * 11}%`,
              top: `${18 + (i % 3) * 22}%`,
              animationDelay: `${i * 0.35}s`,
              opacity: 0.4 + (i % 3) * 0.15,
            }}
          />
        ))}

        <div className="absolute left-5 top-4 flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
          </span>
          <span className="text-[11px] font-semibold tracking-[0.18em] text-accent">FUSION ENGINE</span>
        </div>
      </div>

      <p className="text-center text-sm font-semibold text-white">Synthesizing best answer...</p>
      <p className="mt-1 text-center text-sm text-slate-400">{statusLine}</p>
      <div className="mt-4 overflow-hidden rounded-full border border-white/10 bg-black/20">
        <div
          className="relative h-2 overflow-hidden rounded-full transition-all duration-700"
          style={{ width: `${progress}%` }}
        >
          <div className="absolute inset-0 bg-gradient-to-r from-cyan-400 via-accent to-emerald-300" />
          <div className="absolute inset-0 animate-[mmShimmer_1.6s_linear_infinite] bg-gradient-to-r from-transparent via-white/35 to-transparent" />
        </div>
      </div>

      <style>{`
        @keyframes mmSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes mmPulse {
          0%, 100% { transform: scale(0.92); opacity: 0.55; }
          50% { transform: scale(1.08); opacity: 1; }
        }
        @keyframes mmBeam {
          0%, 100% { opacity: 0.15; transform: translateY(-50%) scaleX(0.6); }
          50% { opacity: 0.85; transform: translateY(-50%) scaleX(1); }
        }
        @keyframes mmStream {
          0% { left: -35%; opacity: 0.2; }
          50% { opacity: 1; }
          100% { left: 105%; opacity: 0.15; }
        }
        @keyframes mmFloat {
          0%, 100% { transform: translateY(0) scale(1); opacity: 0.3; }
          50% { transform: translateY(-10px) scale(1.3); opacity: 0.9; }
        }
        @keyframes mmSweep {
          0% { transform: translateX(-30%); opacity: 0; }
          40% { opacity: 1; }
          100% { transform: translateX(180%); opacity: 0; }
        }
        @keyframes mmShimmer {
          0% { transform: translateX(-120%); }
          100% { transform: translateX(220%); }
        }
      `}</style>
    </div>
  );
}

import { Link } from "react-router-dom";

export function Home() {
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <p className="text-xs font-semibold uppercase tracking-widest text-accent">Choose a mode</p>
      <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
        AI Fusion workspace
      </h1>
      <p className="text-slate-400">
        Ask one question and let multiple models debate, merge strengths, and produce one high-quality
        answer. Resume remains a dedicated structured workflow.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          to="/debate"
          className="group rounded-xl border border-white/10 bg-surface p-5 shadow-xl transition hover:border-accent/40"
        >
          <h2 className="text-lg font-semibold text-white group-hover:text-accent">Fusion mode</h2>
          <p className="mt-2 text-sm text-slate-400">
            Multiple models debate, chair synthesizes one answer, with contribution scoring.
          </p>
        </Link>
        <Link
          to="/resume"
          className="group rounded-xl border border-white/10 bg-surface p-5 shadow-xl transition hover:border-accent/40"
        >
          <h2 className="text-lg font-semibold text-white group-hover:text-accent">Resume mode</h2>
          <p className="mt-2 text-sm text-slate-400">
            JD + file → keyword gaps → tailored Word doc. Optional diff and refine.
          </p>
        </Link>
      </div>
      <p className="text-xs text-slate-500">
        API endpoint: <code className="font-mono text-slate-400">POST /api/debate</code>.
      </p>
    </div>
  );
}

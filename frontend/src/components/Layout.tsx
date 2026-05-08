import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

export function Layout({ children }: { children: ReactNode }) {
  const loc = useLocation();
  const tab = (path: string) =>
    loc.pathname === path
      ? "border-accent text-white"
      : "border-transparent text-slate-400 hover:text-slate-200";

  return (
    <div className="min-h-screen bg-[#0c0e12] text-slate-100">
      <div
        className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(110,231,183,0.12),transparent)]"
        aria-hidden
      />
      <header className="relative z-10 border-b border-white/10 bg-[#141820]/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="font-semibold tracking-tight text-white">
            Model Mix
          </Link>
          <nav className="flex gap-1 text-sm font-medium">
            <Link
              to="/chat"
              className={`rounded-md border-b-2 px-3 py-2 transition-colors ${tab("/chat")}`}
            >
              Chat
            </Link>
            <Link
              to="/debate"
              className={`rounded-md border-b-2 px-3 py-2 transition-colors ${tab("/debate")}`}
            >
              Debate
            </Link>
            <Link
              to="/resume"
              className={`rounded-md border-b-2 px-3 py-2 transition-colors ${tab("/resume")}`}
            >
              Resume
            </Link>
          </nav>
        </div>
      </header>
      <main className="relative z-10 mx-auto max-w-5xl px-4 py-8">{children}</main>
    </div>
  );
}

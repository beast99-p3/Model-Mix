import { useState } from "react";
import ReactDiffViewer from "react-diff-viewer-continued";
import { formatFastApiError } from "../lib/apiError";
import { consumeSseStream } from "../lib/sse";

type Analyze = {
  jd_keywords: string[];
  keyword_hits: { keyword: string; found_in_resume: boolean }[];
  gaps: string[];
  resume_excerpt: string;
  resume_text: string;
};

export function ResumeMode() {
  const [jdText, setJdText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [prefs, setPrefs] = useState("");
  const [analyze, setAnalyze] = useState<Analyze | null>(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [artifactId, setArtifactId] = useState<string | null>(null);
  const [draftMd, setDraftMd] = useState<string | null>(null);
  const [score, setScore] = useState<number | null>(null);
  const [refine, setRefine] = useState("");
  const [error, setError] = useState<string | null>(null);

  const pushLog = (line: string) => setLog((l) => [...l, line]);

  async function runAnalyze() {
    setError(null);
    if (!file || jdText.trim().length < 20) {
      setError("Need a job description (20+ chars) and a resume file.");
      return;
    }
    setBusy(true);
    setAnalyze(null);
    setArtifactId(null);
    setDraftMd(null);
    setScore(null);
    setLog([]);
    const fd = new FormData();
    fd.append("jd_text", jdText);
    fd.append("file", file);
    const res = await fetch("/api/resume/analyze", { method: "POST", body: fd });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setError(formatFastApiError(data, res.statusText));
      setBusy(false);
      return;
    }
    setAnalyze(data as Analyze);
    setBusy(false);
  }

  async function loadDraftForArtifact(id: string) {
    const res = await fetch(`/api/resume/artifact/${id}/meta`);
    if (!res.ok) return;
    const m = (await res.json()) as { draft_markdown?: string };
    if (m.draft_markdown) setDraftMd(m.draft_markdown);
  }

  /* Wrapped generate completion */
  async function runGenerateFixed() {
    setError(null);
    if (!analyze) {
      setError("Run analyze first.");
      return;
    }
    const rt = analyze.resume_text?.trim() ?? "";
    const jd = jdText.trim();
    if (rt.length < 20 || jd.length < 20) {
      setError(
        "Resume text and job description must each be at least 20 characters (API rule). Lengthen the JD or use a fuller resume extract.",
      );
      return;
    }
    setBusy(true);
    setLog([]);
    setArtifactId(null);
    setDraftMd(null);
    setScore(null);
    let completedId: string | null = null;

    const res = await fetch("/api/resume/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: analyze.resume_text,
        jd_text: jdText,
        preferences: prefs || null,
        keywords: analyze.jd_keywords,
      }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => null);
      setError(formatFastApiError(errBody, res.statusText));
      setBusy(false);
      return;
    }

    try {
      await consumeSseStream(res, (ev) => {
        if (ev.stage === "error" && typeof ev.message === "string") {
          throw new Error(ev.message);
        }
        if (typeof ev.message === "string") {
          pushLog(`${String(ev.stage)}: ${ev.message}`);
        }
        if (ev.stage === "ats_check" && typeof ev.score === "number") {
          setScore(ev.score);
        }
        if (ev.stage === "complete" && typeof ev.artifact_id === "string") {
          completedId = ev.artifact_id;
        }
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
      return;
    }

    if (completedId) {
      setArtifactId(completedId);
      await loadDraftForArtifact(completedId);
    }
    setBusy(false);
  }

  async function runRefine() {
    setError(null);
    if (!artifactId || refine.trim().length < 3) {
      setError("Need an artifact and feedback (3+ chars).");
      return;
    }
    setBusy(true);
    const res = await fetch("/api/resume/refine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        artifact_id: artifactId,
        feedback: refine,
        jd_text: jdText,
      }),
    });
    const data = await res.json().catch(() => null) as {
      detail?: unknown;
      artifact_id?: string;
    };
    if (!res.ok) {
      setError(formatFastApiError(data, res.statusText));
      setBusy(false);
      return;
    }
    if (data?.artifact_id) {
      setArtifactId(data.artifact_id);
      await loadDraftForArtifact(data.artifact_id);
    }
    setRefine("");
    setBusy(false);
  }

  return (
    <div className="space-y-8 pb-24">
      <div>
        <h1 className="text-2xl font-bold text-white">Resume mode</h1>
        <p className="mt-1 text-sm text-slate-400">
          Upload resume + paste JD → analyze gaps → generate a tailored .docx. Refine with natural
          language feedback.
        </p>
      </div>

      <section className="grid gap-6 rounded-xl border border-white/10 bg-surface p-5 shadow-xl lg:grid-cols-2">
        <div className="space-y-3">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Job description
          </label>
          <textarea
            className="h-48 w-full rounded-lg border border-white/10 bg-black/30 p-3 text-sm text-white focus:border-accent/50 focus:outline-none"
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the full job description…"
          />
        </div>
        <div className="space-y-3">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Resume file (.docx, .pdf, .txt)
          </label>
          <input
            type="file"
            accept=".docx,.pdf,.txt"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-accent file:px-3 file:py-2 file:text-sm file:font-semibold file:text-emerald-950"
          />
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Optional preferences
          </label>
          <textarea
            className="h-24 w-full rounded-lg border border-white/10 bg-black/30 p-3 text-sm text-white focus:border-accent/50 focus:outline-none"
            value={prefs}
            onChange={(e) => setPrefs(e.target.value)}
            placeholder="e.g. one page, emphasize leadership, keep education short…"
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => void runAnalyze()}
            className="w-full rounded-lg bg-white/10 py-2 text-sm font-semibold text-white hover:bg-white/15 disabled:opacity-50"
          >
            Analyze
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {analyze && (
        <section className="space-y-4 rounded-xl border border-white/10 bg-surface p-5 shadow-xl">
          <h2 className="text-lg font-semibold text-white">Analysis</h2>
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <h3 className="text-xs font-semibold uppercase text-slate-500">Keywords</h3>
              <ul className="mt-2 flex flex-wrap gap-2">
                {analyze.keyword_hits.map((k) => (
                  <li
                    key={k.keyword}
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      k.found_in_resume
                        ? "bg-emerald-500/20 text-emerald-200"
                        : "bg-amber-500/20 text-amber-100"
                    }`}
                  >
                    {k.keyword}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase text-slate-500">Gaps</h3>
              <ul className="mt-2 list-inside list-disc text-sm text-slate-300">
                {analyze.gaps.map((g, i) => (
                  <li key={i}>{g}</li>
                ))}
              </ul>
            </div>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void runGenerateFixed()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-emerald-950 disabled:opacity-50"
          >
            Generate tailored resume
          </button>
        </section>
      )}

      {log.length > 0 && (
        <section className="rounded-xl border border-white/10 bg-black/30 p-4 font-mono text-xs text-slate-400">
          {log.map((l, i) => (
            <div key={i}>{l}</div>
          ))}
          {score !== null && <div className="mt-2 text-accent">Keyword coverage score: {score}</div>}
        </section>
      )}

      {artifactId && (
        <section className="space-y-4 rounded-xl border border-white/10 bg-surface p-5 shadow-xl">
          <div className="flex flex-wrap items-center gap-3">
            <a
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-emerald-950"
              href={`/api/resume/download/${artifactId}`}
            >
              Download .docx
            </a>
            <span className="text-xs text-slate-500">Artifact: {artifactId.slice(0, 8)}…</span>
          </div>

          {analyze && draftMd && (
            <div className="overflow-hidden rounded-lg border border-white/10">
              <ReactDiffViewer
                oldValue={analyze.resume_text}
                newValue={draftMd}
                splitView
                leftTitle="Extracted original"
                rightTitle="AI draft (markdown)"
                useDarkTheme
              />
            </div>
          )}

          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase text-slate-500">Refine</label>
            <textarea
              className="h-24 w-full rounded-lg border border-white/10 bg-black/30 p-3 text-sm text-white focus:border-accent/50 focus:outline-none"
              value={refine}
              onChange={(e) => setRefine(e.target.value)}
              placeholder="e.g. Strengthen bullet 3 under Experience; shorten summary…"
            />
            <button
              type="button"
              disabled={busy}
              onClick={() => void runRefine()}
              className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-white hover:bg-white/15 disabled:opacity-50"
            >
              Apply refinement
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

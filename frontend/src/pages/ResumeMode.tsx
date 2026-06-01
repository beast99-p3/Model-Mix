import { useEffect, useState } from "react";
import ReactDiffViewer from "react-diff-viewer-continued";
import { ResumeAnalyzeLoader } from "../components/ResumeAnalyzeLoader";
import { ResumeGenerateLoader } from "../components/ResumeGenerateLoader";
import { formatFastApiError } from "../lib/apiError";
import { consumeSseStream } from "../lib/sse";

type Analyze = {
  jd_keywords: string[];
  keyword_hits: { keyword: string; found_in_resume: boolean }[];
  gaps: string[];
  resume_excerpt: string;
  resume_text: string;
  source_upload_id?: string | null;
};

const GENERATE_STAGES = [
  "Four models drafting in parallel…",
  "Crossfire: refining each draft…",
  "Chair merging best version…",
  "Checking keyword coverage…",
  "Exporting Word document…",
];

export function ResumeMode() {
  const [jdText, setJdText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [prefs, setPrefs] = useState("");
  const [analyze, setAnalyze] = useState<Analyze | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [refining, setRefining] = useState(false);
  const [savingDownloads, setSavingDownloads] = useState(false);
  const [analyzePhase, setAnalyzePhase] = useState(0);
  const [generatePhase, setGeneratePhase] = useState(0);
  const [log, setLog] = useState<string[]>([]);
  const [artifactId, setArtifactId] = useState<string | null>(null);
  const [editableDraft, setEditableDraft] = useState("");
  const [editCommand, setEditCommand] = useState("");
  const [score, setScore] = useState<number | null>(null);
  const [showDiff, setShowDiff] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const busy = analyzing || generating || refining || savingDownloads;

  useEffect(() => {
    if (!analyzing) return;
    const t = window.setInterval(() => setAnalyzePhase((p) => p + 1), 1800);
    return () => window.clearInterval(t);
  }, [analyzing]);

  const pushLog = (line: string) => {
    setLog((l) => [...l, line]);
    setGeneratePhase((p) => Math.min(GENERATE_STAGES.length - 1, p + 1));
  };

  async function runAnalyze() {
    setError(null);
    if (!file || jdText.trim().length < 20) {
      setError("Need a job description (20+ chars) and a resume file.");
      return;
    }
    setAnalyzing(true);
    setAnalyzePhase(0);
    setAnalyze(null);
    setArtifactId(null);
    setEditableDraft("");
    setScore(null);
    setLog([]);
    setShowDiff(false);

    const fd = new FormData();
    fd.append("jd_text", jdText);
    fd.append("file", file);

    try {
      const res = await fetch("/api/resume/analyze", { method: "POST", body: fd });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(formatFastApiError(data, res.statusText));
        return;
      }
      setAnalyze(data as Analyze);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  }

  async function runGenerate() {
    setError(null);
    if (!analyze) {
      setError("Run analyze first.");
      return;
    }
    const rt = analyze.resume_text?.trim() ?? "";
    const jd = jdText.trim();
    if (rt.length < 20 || jd.length < 20) {
      setError(
        "Resume text and job description must each be at least 20 characters. Lengthen the JD or use a fuller resume.",
      );
      return;
    }

    setGenerating(true);
    setGeneratePhase(0);
    setLog([]);
    setArtifactId(null);
    setEditableDraft("");
    setScore(null);
    setShowDiff(false);

    let completedId: string | null = null;
    let draftFromStream: string | null = null;

    const res = await fetch("/api/resume/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: analyze.resume_text,
        jd_text: jdText,
        preferences: prefs || null,
        keywords: analyze.jd_keywords,
        source_upload_id: analyze.source_upload_id ?? null,
      }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => null);
      setError(formatFastApiError(errBody, res.statusText));
      setGenerating(false);
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
          if (typeof ev.draft_markdown === "string") {
            draftFromStream = ev.draft_markdown;
          }
        }
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setGenerating(false);
      return;
    }

    if (completedId) {
      setArtifactId(completedId);
      if (draftFromStream) {
        setEditableDraft(draftFromStream);
      } else {
        const metaRes = await fetch(`/api/resume/artifact/${completedId}/meta`);
        if (metaRes.ok) {
          const m = (await metaRes.json()) as { draft_markdown?: string };
          if (m.draft_markdown) setEditableDraft(m.draft_markdown);
        }
      }
    }
    setGenerating(false);
  }

  async function saveDraftExports(): Promise<boolean> {
    if (!artifactId || !editableDraft.trim()) return false;
    const res = await fetch("/api/resume/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ artifact_id: artifactId, draft_markdown: editableDraft }),
    });
    return res.ok;
  }

  async function downloadResume(format: "docx" | "pdf") {
    setError(null);
    if (!artifactId) return;
    setSavingDownloads(true);
    const saved = await saveDraftExports();
    setSavingDownloads(false);
    if (!saved) {
      setError("Could not save draft before download.");
      return;
    }
    window.location.href = `/api/resume/download/${artifactId}?format=${format}`;
  }

  async function runEditCommand() {
    setError(null);
    if (!artifactId || editCommand.trim().length < 3) {
      setError("Enter an edit command (3+ characters).");
      return;
    }
    if (!editableDraft.trim()) {
      setError("No draft to edit.");
      return;
    }

    setRefining(true);
    const res = await fetch("/api/resume/refine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        artifact_id: artifactId,
        feedback: editCommand,
        jd_text: jdText,
        resume_text: editableDraft,
      }),
    });

    const data = (await res.json().catch(() => null)) as {
      detail?: unknown;
      artifact_id?: string;
      draft_markdown?: string;
    };

    if (!res.ok) {
      setError(formatFastApiError(data, res.statusText));
      setRefining(false);
      return;
    }

    if (data?.artifact_id) {
      setArtifactId(data.artifact_id);
      if (data.draft_markdown) {
        setEditableDraft(data.draft_markdown);
      } else {
        const metaRes = await fetch(`/api/resume/artifact/${data.artifact_id}/meta`);
        if (metaRes.ok) {
          const m = (await metaRes.json()) as { draft_markdown?: string };
          if (m.draft_markdown) setEditableDraft(m.draft_markdown);
        }
      }
    }
    setEditCommand("");
    setRefining(false);
  }

  return (
    <div className="space-y-8 pb-24">
      <div>
        <h1 className="text-2xl font-bold text-white">Resume mode</h1>
        <p className="mt-1 text-sm text-slate-400">
          Upload resume + paste JD → analyze gaps → four models fuse one tailored copy (same format as
          your source) → edit with natural-language commands.
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
            disabled={busy}
          />
        </div>
        <div className="space-y-3">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Resume file (.docx, .pdf, .txt)
          </label>
          <input
            type="file"
            accept=".docx,.pdf,.txt"
            disabled={busy}
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
            placeholder="e.g. emphasize leadership, keep one page — layout changes only if you ask here"
            disabled={busy}
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => void runAnalyze()}
            className="w-full rounded-lg bg-white/10 py-2 text-sm font-semibold text-white hover:bg-white/15 disabled:opacity-50"
          >
            {analyzing ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      </section>

      {analyzing && <ResumeAnalyzeLoader phase={analyzePhase} />}

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {analyze && !analyzing && (
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
            onClick={() => void runGenerate()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-emerald-950 disabled:opacity-50"
          >
            {generating ? "Generating…" : "Generate tailored resume (fusion)"}
          </button>
        </section>
      )}

      {generating && (
        <ResumeGenerateLoader
          statusLine={log.at(-1) ?? GENERATE_STAGES[generatePhase]}
          progress={12 + generatePhase * 16}
        />
      )}

      {log.length > 0 && !generating && (
        <section className="rounded-xl border border-white/10 bg-black/30 p-4 font-mono text-xs text-slate-400">
          {log.map((l, i) => (
            <div key={i}>{l}</div>
          ))}
          {score !== null && <div className="mt-2 text-accent">Keyword coverage score: {score}</div>}
        </section>
      )}

      {editableDraft && artifactId && (
        <section className="space-y-4 rounded-xl border border-accent/20 bg-surface p-5 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Generated resume</h2>
              <p className="mt-0.5 text-xs text-slate-400">
                Same layout as your source. Edit text directly or type a command below.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setShowDiff((v) => !v)}
                className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-white/5"
              >
                {showDiff ? "Hide comparison" : "Compare to original"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void downloadResume("docx")}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-emerald-950 disabled:opacity-50"
              >
                Download .docx
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void downloadResume("pdf")}
                className="rounded-lg border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent disabled:opacity-50"
              >
                Download .pdf
              </button>
            </div>
          </div>

          <textarea
            className="min-h-[420px] w-full resize-y rounded-lg border border-white/10 bg-black/30 p-4 font-mono text-sm leading-relaxed text-slate-100 focus:border-accent/50 focus:outline-none"
            value={editableDraft}
            onChange={(e) => setEditableDraft(e.target.value)}
            disabled={refining}
            spellCheck={false}
          />

          <div className="rounded-lg border border-white/10 bg-black/20 p-4">
            <label htmlFor="edit-command" className="mb-2 block text-xs font-semibold uppercase text-slate-500">
              Edit command
            </label>
            <textarea
              id="edit-command"
              className="h-20 w-full rounded-lg border border-white/10 bg-black/30 p-3 text-sm text-white focus:border-accent/50 focus:outline-none"
              value={editCommand}
              onChange={(e) => setEditCommand(e.target.value)}
              disabled={refining}
              placeholder='e.g. "Strengthen the second bullet under Experience" or "Add Python to skills if missing"'
            />
            <button
              type="button"
              disabled={refining || editCommand.trim().length < 3}
              onClick={() => void runEditCommand()}
              className="mt-2 rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-white hover:bg-white/15 disabled:opacity-50"
            >
              {refining ? "Applying edit…" : "Apply edit command"}
            </button>
          </div>

          {refining && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
              Updating resume while preserving format…
            </div>
          )}

          {showDiff && analyze && (
            <div className="overflow-hidden rounded-lg border border-white/10">
              <ReactDiffViewer
                oldValue={analyze.resume_text}
                newValue={editableDraft}
                splitView
                leftTitle="Original (source format)"
                rightTitle="Generated copy"
                useDarkTheme
              />
            </div>
          )}
        </section>
      )}
    </div>
  );
}

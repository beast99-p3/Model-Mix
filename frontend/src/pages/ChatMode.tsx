import { useCallback, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { formatFastApiError } from "../lib/apiError";
import { consumeSseStream } from "../lib/sse";

type Msg = { role: "user" | "assistant"; content: string };

function withNonEmptyContent(msgs: Msg[]): Msg[] {
  return msgs
    .map((m) => ({ ...m, content: m.content.trim() }))
    .filter((m) => m.content.length > 0);
}

export function ChatMode() {
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const scrollDown = () => {
    requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }));
  };

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setError(null);
    setBusy(true);
    setDraft("");
    const history = withNonEmptyContent(messages);
    const next: Msg[] = [...history, { role: "user", content: text }];
    setMessages(next);
    setStreaming("");
    scrollDown();

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        messages: next,
      }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => null);
      setError(formatFastApiError(body, res.statusText));
      setBusy(false);
      return;
    }

    let assistant = "";
    try {
      await consumeSseStream(res, (ev) => {
        const t = ev.type;
        if (t === "chat_id" && typeof ev.chat_id === "string") {
          setChatId(ev.chat_id);
        }
        if (t === "delta" && typeof ev.text === "string") {
          assistant += ev.text;
          setStreaming(assistant);
          scrollDown();
        }
        if (t === "error" && typeof ev.message === "string") {
          throw new Error(ev.message);
        }
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
      setStreaming("");
      return;
    }

    if (assistant.trim().length > 0) {
      setMessages((m) => [...m, { role: "assistant", content: assistant }]);
    } else {
      setError("The model returned an empty reply. Check your API configuration and try again.");
    }
    setStreaming("");
    setBusy(false);
    scrollDown();
  }, [busy, chatId, draft, messages]);

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold text-white">Chat mode</h1>
        <p className="mt-1 text-sm text-slate-400">
          Streaming assistant replies (SSE). History is stored server-side per chat id.
        </p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-white/10 bg-surface shadow-xl">
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && !streaming && (
            <p className="text-sm text-slate-500">Send a message to start.</p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "ml-8 rounded-lg bg-white/5 p-3 text-slate-100"
                  : "mr-8 rounded-lg border border-white/10 bg-black/20 p-3 text-slate-200"
              }
            >
              {m.role === "assistant" ? (
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-sm">{m.content}</p>
              )}
            </div>
          ))}
          {streaming && (
            <div className="mr-8 rounded-lg border border-accent/30 bg-black/20 p-3 text-slate-200">
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown>{streaming}</ReactMarkdown>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="border-t border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="flex gap-2 border-t border-white/10 p-3">
          <textarea
            className="min-h-[48px] flex-1 resize-none rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-accent/50 focus:outline-none"
            placeholder="Message… (Ctrl+Enter to send)"
            value={draft}
            disabled={busy}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button
            type="button"
            onClick={() => void send()}
            disabled={busy || !draft.trim()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-emerald-950 disabled:opacity-50"
          >
            {busy ? "…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

const $ = (id) => document.getElementById(id);

const panelInput = $("panel-input");
const panelStatus = $("panel-status");
const panelResult = $("panel-result");
const questionEl = $("question");
const showTranscriptEl = $("showTranscript");
const submitBtn = $("submitBtn");
const newQuestionBtn = $("newQuestionBtn");
const statusTitle = $("statusTitle");
const statusSub = $("statusSub");
const finalAnswerEl = $("finalAnswer");
const transcriptWrap = $("transcriptWrap");
const transcriptEl = $("transcript");
const errorMsg = $("errorMsg");

const STATUS_STEPS = [
  { title: "Panel is debating…", sub: "Round 1: independent answers" },
  { title: "Panel is debating…", sub: "Round 2: critique & revised answers" },
  { title: "Almost there…", sub: "Chair is synthesizing one answer" },
];

function showError(text) {
  errorMsg.textContent = text;
  errorMsg.classList.remove("hidden");
}

function hideError() {
  errorMsg.classList.add("hidden");
  errorMsg.textContent = "";
}

function setLoading(loading) {
  submitBtn.disabled = loading;
  submitBtn.classList.toggle("loading", loading);
}

function showPanel(which) {
  panelInput.classList.toggle("hidden", which !== "input");
  panelStatus.classList.toggle("hidden", which !== "status");
  panelResult.classList.toggle("hidden", which !== "result");
}

let statusTimer = null;

function startStatusSequence() {
  let i = 0;
  const tick = () => {
    const step = STATUS_STEPS[Math.min(i, STATUS_STEPS.length - 1)];
    statusTitle.textContent = step.title;
    statusSub.textContent = step.sub;
    i += 1;
  };
  tick();
  statusTimer = window.setInterval(tick, 12000);
}

function stopStatusSequence() {
  if (statusTimer !== null) {
    window.clearInterval(statusTimer);
    statusTimer = null;
  }
}

function renderTranscript(entries) {
  transcriptEl.innerHTML = "";
  for (const e of entries) {
    const block = document.createElement("div");
    block.className = "turn";
    block.innerHTML = `
      <div class="turn-meta">${escapeHtml(e.round_name)} · ${escapeHtml(e.debater_id)}</div>
      <div class="turn-body">${escapeHtml(e.text)}</div>
    `;
    transcriptEl.appendChild(block);
  }
}

function formatApiError(data, res) {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d))
    return d.map((x) => (x && typeof x.msg === "string" ? x.msg : JSON.stringify(x))).join("; ");
  if (d && typeof d === "object") return JSON.stringify(d);
  return res.statusText || "Request failed";
}

function escapeHtml(s) {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function runDebate() {
  hideError();
  const question = questionEl.value.trim();
  if (!question) {
    showError("Please enter a question.");
    questionEl.focus();
    return;
  }

  setLoading(true);
  showPanel("status");
  startStatusSequence();
  finalAnswerEl.classList.remove("visible");
  transcriptWrap.classList.add("hidden");

  try {
    const res = await fetch("/api/debate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        show_transcript: showTranscriptEl.checked,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(formatApiError(data, res));
    }

    stopStatusSequence();
    showPanel("result");

    finalAnswerEl.textContent = data.final_answer ?? "";
    requestAnimationFrame(() => finalAnswerEl.classList.add("visible"));

    if (showTranscriptEl.checked && Array.isArray(data.transcript) && data.transcript.length) {
      transcriptWrap.classList.remove("hidden");
      renderTranscript(data.transcript);
    } else {
      transcriptWrap.classList.add("hidden");
    }

    panelResult.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    stopStatusSequence();
    showPanel("input");
    showError(err instanceof Error ? err.message : String(err));
  } finally {
    setLoading(false);
  }
}

submitBtn.addEventListener("click", runDebate);

questionEl.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    runDebate();
  }
});

newQuestionBtn.addEventListener("click", () => {
  stopStatusSequence();
  showPanel("input");
  finalAnswerEl.textContent = "";
  finalAnswerEl.classList.remove("visible");
  transcriptWrap.classList.add("hidden");
  questionEl.focus();
});

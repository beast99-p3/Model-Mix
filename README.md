# Model Mix

Model Mix is a multi-model fusion app:

- **Fusion mode** (`/debate`): multiple models debate in two rounds and a chair synthesizes one final answer.
- **Resume mode** (`/resume`): upload a resume + job description → analyze gaps & keywords → **fusion-tailored draft** (four debaters + chair) → edit → download **`.docx` / `.pdf`** with layout preserved from your upload.
- API-first backend via FastAPI.

---

## Architecture

- **Shared:** FastAPI, `src/llm/unified.py` (async completions + streaming), `src/config.py` (env-driven models), `structlog` JSON logs (`src/logging_conf.py`).
- **Chat only:** SQLite (`data/app.db`) for message history; streaming `text/event-stream`.
- **Resume only:** extraction (`src/resume/extract.py`), format/layout (`src/resume/format.py`), ATS scoring (`src/resume/ats_score.py`), export (`src/resume/export.py`), fusion pipeline (`src/resume/pipeline.py` + `src/debate.py`), artifacts under `data/outputs/`, source uploads under `data/uploads/`.
- **Jobs:** `src/resume/jobs.py` defines an **`InMemoryJobQueue`** swappable for Redis/RQ later; the current **generate** path streams in-process (no Redis required).

The legacy static debate page under `web/` is **not** the main UI anymore; use the **React** app in `frontend/`.

---

## Resume mode (workflow)

1. **Analyze** — Upload `.docx`, `.pdf`, or `.txt` and paste the job description. The backend extracts text, stores the source file for format-aware export, and returns:
   - JD keywords and which appear in your resume
   - Gap bullets (weak or missing vs the JD)
   - **`ats_match`** — estimated ATS pass similarity (0–100%) for the **original** resume
2. **Generate** — Four models + chair tailor wording to the JD while preserving your resume’s structure (sections, bullets, line breaks). SSE stages include fusion rounds and an ATS re-score on the **tailored** draft.
3. **Edit** — Adjust the draft in the UI or send natural-language refine commands; ATS score updates after refine when keywords are available.
4. **Download** — Save edits, then download **Word** or **PDF**. If you uploaded **`.docx`**, export clones paragraph styles from your file when possible.

**Format tips:** `.docx` uploads give the closest match to your original styling. PDFs are supported; extraction normalizes odd characters (e.g. `■` → `-`) and keeps skill bullet line wraps where appropriate.

---

## ATS match score

Resume mode shows an **ATS match** percentage (not a guarantee from any specific ATS vendor). It is a weighted estimate:

| Component | Weight | Meaning |
|-----------|--------|---------|
| **Keyword coverage** | 55% | Share of JD keywords/phrases found in the resume (phrase-aware matching) |
| **JD alignment** | 20% | Vocabulary overlap between resume and job description |
| **Gap readiness** | 25% | Penalty from analyze “gaps” (original resume only; tailored score focuses on keyword/JD fit) |

Labels: **Strong match** (85%+), **Good match** (70%+), **Moderate match** (55%+), **Needs improvement** (&lt;55%).

The UI shows:

- A ring chart and summary after **Analyze** (baseline)
- An updated score after **Generate**, with **+X% vs original** when the tailored resume improves
- Breakdown chips for keywords, JD terms, and gap readiness

Implementation: `src/resume/ats_score.py`; returned as `ats_match` on analyze/refine JSON and in generate SSE (`ats_check`, `complete`).

---

## Quick start

**Backend**

```bash
cd "Model Mix"
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # add keys
python -m uvicorn server:app --reload --reload-dir src --reload-include server.py --host 127.0.0.1 --port 8000
```

Do **not** run the bare `uvicorn` command in Git Bash (it is often missing from `PATH` even after `pip install uvicorn`). Use **`python -m uvicorn`** instead, or from the project root run **`./run_server.sh`** (Git Bash) or **`run_server.bat`** (Command Prompt).

**Git Bash + paths with spaces:** quote any full Windows path, e.g.  
`"/c/Users/you/OneDrive - Your School/Projects/Model Mix/.venv/Scripts/python.exe" -m uvicorn server:app --reload --reload-dir src --reload-include server.py --host 127.0.0.1 --port 8000`

**Frontend (development)**

```bash
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173** — Vite proxies `/api` to the backend.

**Frontend (production build served by FastAPI)**

```bash
cd frontend
npm run build
# then run `python -m uvicorn ...` as above — visit http://127.0.0.1:8000
```

---

## Environment

See `.env.example`. Important variables:

- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` — for direct OpenAI / Anthropic APIs (not Bedrock).
- **Amazon Bedrock** — either (**a**) a **Bedrock API key**: set **`AWS_BEARER_TOKEN_BEDROCK`** and **`AWS_DEFAULT_REGION`** ([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-use.html)), or (**b**) classic IAM programmatic access: **`AWS_ACCESS_KEY_ID`**, **`AWS_SECRET_ACCESS_KEY`**, **`AWS_DEFAULT_REGION`**, or (**c**) **`AWS_PROFILE`**. A Bedrock API key is **not** the same as `AWS_ACCESS_KEY_ID`. Set `CHAT_PROVIDER=bedrock` and `CHAT_MODEL` to a Bedrock **model id** where you want Bedrock. Resume stages follow **`RESUME_*_PROVIDER`** / **`RESUME_*_MODEL`** (defaults follow `CHAT_*`).
- **Fusion panel seats** — configure up to four Bedrock-backed seats and one chair:
  - `DEBATER_AURORA_PROVIDER` / `DEBATER_AURORA_MODEL`
  - `DEBATER_QUARTZ_PROVIDER` / `DEBATER_QUARTZ_MODEL`
  - `DEBATER_NOVA_PROVIDER` / `DEBATER_NOVA_MODEL`
  - `DEBATER_LYRIC_PROVIDER` / `DEBATER_LYRIC_MODEL`
  - `CHAIR_PROVIDER` / `CHAIR_MODEL`
  - UI labels show actual provider/model (for example `Anthropic - us.anthropic.claude-sonnet-4-6`), not internal seat ids.
- `DATA_DIR` — optional; defaults to `./data` (SQLite + generated `.docx`).
- `CHAT_*`, `RESUME_*`, `CHAIR_*` — optional per-stage model overrides.

---

## HTTP API (summary)

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/api/health` | Liveness |
| `POST` | `/api/resume/analyze` | `multipart/form-data`: `jd_text`, `file` (.docx / .pdf / .txt). Returns keywords, gaps, `resume_text`, `source_upload_id`, **`ats_match`**. |
| `POST` | `/api/resume/generate` | JSON: `resume_text`, `jd_text`, `preferences?`, `keywords`, `gaps?`, `source_upload_id?`. SSE: `prepare`, `draft`, `fusion_round1`, `fusion_round2`, `fusion_chair`, `ats_check` (includes **`ats_match`**), `export`, `complete` (`artifact_id`, `draft_markdown`, `ats_match`). Same four-model fusion panel as `/api/debate`. |
| `POST` | `/api/resume/refine` | JSON: `artifact_id`, `feedback`, `jd_text?`, `resume_text?`, `keywords?`, `gaps?`. New `artifact_id`, `draft_markdown`, optional **`ats_match`**. |
| `POST` | `/api/resume/save` | JSON: `artifact_id`, `draft_markdown`. Persists edits before download. |
| `GET` | `/api/resume/download/{artifact_id}?format=docx\|pdf` | Download tailored resume |
| `GET` | `/api/resume/artifact/{artifact_id}/meta` | Draft + source metadata (for diff UI) |
| `POST` | `/api/debate` | Fusion flow; JSON `question`, `show_transcript?`. Returns `final_answer`, optional `transcript`, and `analytics` (confidence, consensus, per-model contribution). |

Full schemas: **http://127.0.0.1:8000/docs**

### `ats_match` object (analyze / generate / refine)

| Field | Type | Description |
|-------|------|-------------|
| `score_pct` | float | Overall ATS match 0–100 |
| `keyword_coverage_pct` | float | JD keyword hit rate |
| `jd_alignment_pct` | float | JD vocabulary overlap |
| `gap_readiness_pct` | float | Inverse gap penalty |
| `keywords_matched` / `keywords_total` | int | Counts |
| `gaps_count` | int | Gaps from analyze |
| `label` | string | e.g. `Good match` |
| `summary` | string | Short explanation |
| `keyword_hits` | array | `{ keyword, found_in_resume }` |

---

## CLI (panel debate only)

```bash
python main.py "Your question here"
python main.py "Your question" --show-debate
```

---

## Fusion scoring metrics

`/api/debate` returns scoring fields:

- **`final_confidence_pct`**: blended score derived from relevance to question, model agreement, and overlap between model outputs and the final merged answer.
- **`consensus_pct`**: average pairwise agreement between model round-2 responses before chair synthesis.
- **`debaters[].contribution_pct`**: normalized estimate of how much each model influenced the final answer.

These are heuristic quality signals, useful for comparing runs/model mixes. They are **not** a factual guarantee of correctness.

Implementation note: confidence uses a mix of token overlap and character n-gram similarity, plus a calibration step (baseline) so good fusion runs don't look artificially low due to paraphrasing.

---

## Project layout

```
Model Mix/
├── main.py                 # CLI (debate)
├── server.py               # FastAPI app
├── run_server.sh / .bat    # uvicorn with safe reload dirs
├── requirements.txt
├── .env.example
├── frontend/               # React + Vite + Tailwind
│   ├── src/pages/DebateMode.tsx
│   ├── src/pages/ResumeMode.tsx
│   ├── src/components/AtsScoreCard.tsx
│   ├── src/components/ResumeAnalyzeLoader.tsx
│   ├── src/components/ResumeGenerateLoader.tsx
│   └── dist/               # after npm run build
├── src/
│   ├── api/                # chat_routes, resume_routes, debate_routes, sse helper
│   ├── llm/                # unified async client + optional tiktoken
│   ├── resume/
│   │   ├── extract.py      # docx / pdf / txt extraction
│   │   ├── format.py       # layout, reflow, fusion output cleanup
│   │   ├── ats_score.py    # ATS match percentage
│   │   ├── export.py       # docx / pdf generation
│   │   ├── pipeline.py     # analyze, fusion draft, refine
│   │   ├── artifacts.py    # outputs + source uploads
│   │   └── jobs.py
│   ├── schemas/            # Pydantic models per feature
│   ├── config.py
│   ├── db.py               # SQLite chats
│   ├── clients.py          # sync backends (debate.py)
│   └── debate.py           # fusion panel (debate + resume prompts)
└── web/                    # legacy static debate UI (optional)
```

---

## Dependencies (high level)

- **Must:** `fastapi`, `uvicorn`, `python-multipart`, `python-docx`, `pypdf`, `pdfplumber`, `reportlab`, `openai`, `anthropic`, `structlog`, `tiktoken` (optional estimates in `src/llm/tokens.py`).
- **Frontend:** `react`, `react-router-dom`, `react-markdown`, `react-diff-viewer-continued`, `tailwindcss`.

---

## Roadmap / improvements

1. Wire **resume generate** to **`InMemoryJobQueue`** (or Redis) for cancel/retry and long-running deploys.
2. **Token budgeting** — enforce caps using `tiktoken` before LLM calls.
3. **pytest** + fake LLM for pipeline and ATS scoring tests.
4. **SSE** optional wrapper (`sse-starlette`) for consistency.
5. **Auth** (env password or real SSO) before exposing publicly.
6. **Docker Compose** — API + optional `frontend` dev service.
7. **ATS** — optional LLM-based gap re-check after tailor; employer-specific ATS plugins.

---

## License

Use and modify for your own purposes; add a license file if you open-source the repo.

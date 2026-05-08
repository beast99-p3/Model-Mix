# Model Mix

Two **explicit modes** in one app—users pick the workflow, so routing never “guesses” intent:

| Mode | What it is | UI | API |
|------|------------|----|-----|
| **Chat** | Conversational, markdown, **SSE streaming** | `/chat` | `POST /api/chat` |
| **Resume** | Form + file → analyze → generate **.docx** + optional refine + diff | `/resume` | `POST /api/resume/*` |

A third, separate feature remains the **multi-debater panel** (CLI + `POST /api/debate`): several personas debate; a **chair** synthesizes **one** answer.

---

## Architecture

- **Shared:** FastAPI, `src/llm/unified.py` (async completions + streaming), `src/config.py` (env-driven models), `structlog` JSON logs (`src/logging_conf.py`).
- **Chat only:** SQLite (`data/app.db`) for message history; streaming `text/event-stream`.
- **Resume only:** `python-docx` / `pypdf` extraction, pipeline stages in `src/resume/pipeline.py`, artifacts under `data/outputs/`, uploads under `data/uploads/`.
- **Jobs:** `src/resume/jobs.py` defines an **`InMemoryJobQueue`** swappable for Redis/RQ later; the current **generate** path streams in-process (no Redis required).

The legacy static debate page under `web/` is **not** the main UI anymore; use the **React** app in `frontend/`.

---

## Quick start

**Backend**

```bash
cd "Model Mix"
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # add keys
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

Do **not** run the bare `uvicorn` command in Git Bash (it is often missing from `PATH` even after `pip install uvicorn`). Use **`python -m uvicorn`** instead, or from the project root run **`./run_server.sh`** (Git Bash) or **`run_server.bat`** (Command Prompt).

**Git Bash + paths with spaces:** quote any full Windows path, e.g.  
`"/c/Users/you/OneDrive - Your School/Projects/Model Mix/.venv/Scripts/python.exe" -m uvicorn server:app --reload --host 127.0.0.1 --port 8000`

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
- **Using Bedrock and direct APIs together** — put **both** `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` **and** Bedrock auth (`AWS_BEARER_TOKEN_BEDROCK` and/or IAM `AWS_*`) in `.env`. Then choose per feature: e.g. `CHAT_PROVIDER=openai` with `RESUME_DRAFT_PROVIDER=bedrock`, or `CHAIR_PROVIDER=bedrock` with debaters on OpenAI. For the panel, optional env **`DEBATER_<ID>_PROVIDER`** and **`DEBATER_<ID>_MODEL`** override each seat (`analyst`, `skeptic`, `pragmatist` — ids are lowercase in env keys: `DEBATER_SKEPTIC_PROVIDER`). Bedrock paths use `src/llm/bedrock_sync.py` and **`provider=bedrock`** in `src/clients.py` / `src/llm/unified.py`.
- `DATA_DIR` — optional; defaults to `./data` (SQLite + generated `.docx`).
- `CHAT_*`, `RESUME_*`, `CHAIR_*` — optional per-stage model overrides.

---

## HTTP API (summary)

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/api/health` | Liveness |
| `POST` | `/api/chat` | Body: `{ "chat_id"?, "messages": [{role, content}] }`. SSE stream: `chat_id`, `delta`, `done`, `error`. |
| `POST` | `/api/resume/analyze` | `multipart/form-data`: `jd_text`, `file` (.docx / .pdf / .txt). JSON analysis + full `resume_text`. |
| `POST` | `/api/resume/generate` | JSON: `resume_text`, `jd_text`, `preferences?`, `keywords`. SSE: `prepare`, `draft`, `ats_check`, `complete`. |
| `POST` | `/api/resume/refine` | JSON: `artifact_id`, `feedback`, `jd_text?`. New `artifact_id`. |
| `GET` | `/api/resume/download/{artifact_id}` | `.docx` download |
| `GET` | `/api/resume/artifact/{artifact_id}/meta` | Draft + source metadata (for diff UI) |
| `POST` | `/api/debate` | Legacy panel flow; JSON `question`, `show_transcript?`. |

Full schemas: **http://127.0.0.1:8000/docs**

---

## CLI (panel debate only)

```bash
python main.py "Your question here"
python main.py "Your question" --show-debate
```

---

## Panel: how one answer is decided

There is **no vote**. A **chair** model reads the full round-1 / round-2 transcript and **synthesizes** a single user-facing answer (see `CHAIR_SYSTEM` in `src/debate.py`). Quality depends on the chair model and prompts.

---

## Project layout

```
Model Mix/
├── main.py                 # CLI (debate)
├── server.py               # FastAPI app
├── requirements.txt
├── .env.example
├── frontend/               # React + Vite + Tailwind
│   ├── src/pages/ChatMode.tsx
│   ├── src/pages/ResumeMode.tsx
│   └── dist/               # after npm run build
├── src/
│   ├── api/                # chat_routes, resume_routes, debate_routes, sse helper
│   ├── llm/                # unified async client + optional tiktoken
│   ├── resume/             # extract, pipeline, artifacts, jobs
│   ├── schemas/            # Pydantic models per feature
│   ├── config.py
│   ├── db.py               # SQLite chats
│   ├── clients.py          # sync backends (debate.py)
│   └── debate.py
└── web/                    # legacy static debate UI (optional)
```

---

## Dependencies (high level)

- **Must:** `fastapi`, `uvicorn`, `python-multipart`, `python-docx`, `pypdf`, `openai`, `anthropic`, `structlog`, `tiktoken` (optional estimates in `src/llm/tokens.py`).
- **Frontend:** `react`, `react-router-dom`, `react-markdown`, `react-diff-viewer-continued`, `tailwindcss`.

---

## Roadmap / improvements

1. Wire **resume generate** to **`InMemoryJobQueue`** (or Redis) for cancel/retry and long-running deploys.
2. **Token budgeting** — enforce caps using `tiktoken` before LLM calls.
3. **pytest** + fake LLM for pipeline tests.
4. **SSE** optional wrapper (`sse-starlette`) for consistency.
5. **Auth** (env password or real SSO) before exposing publicly.
6. **Docker Compose** — API + optional `frontend` dev service.

---

## License

Use and modify for your own purposes; add a license file if you open-source the repo.

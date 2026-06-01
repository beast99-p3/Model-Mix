#!/usr/bin/env bash
# Git Bash / macOS / Linux: always uses `python -m uvicorn` (no uvicorn on PATH needed).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

RELOAD_FLAGS=(
  --reload
  --reload-dir src
  --reload-include server.py
  --reload-exclude data
  --reload-exclude __pycache__
)

if [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
  exec "$ROOT/.venv/Scripts/python.exe" -m uvicorn server:app "${RELOAD_FLAGS[@]}" --host 127.0.0.1 --port 8000
fi
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" -m uvicorn server:app "${RELOAD_FLAGS[@]}" --host 127.0.0.1 --port 8000
fi
exec python -m uvicorn server:app "${RELOAD_FLAGS[@]}" --host 127.0.0.1 --port 8000

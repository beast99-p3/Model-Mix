@echo off
setlocal
cd /d "%~dp0"
set "UVICORN_FLAGS=--reload --reload-dir src --reload-include server.py --reload-exclude data --reload-exclude __pycache__ --host 127.0.0.1 --port 8000"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m uvicorn server:app %UVICORN_FLAGS%
) else (
  python -m uvicorn server:app %UVICORN_FLAGS%
)

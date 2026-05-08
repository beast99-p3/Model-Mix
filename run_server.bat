@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
) else (
  python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
)

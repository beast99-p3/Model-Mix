"""
FastAPI application: Chat (SSE), Resume pipeline, optional Panel debate.

Dev (API + hot reload):
  python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000

Frontend (Vite):
  cd frontend && npm install && npm run dev
  Vite proxies /api to :8000

Production UI:
  cd frontend && npm run build
  python -m uvicorn server:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.chat_routes import router as chat_router
from src.api.debate_routes import router as debate_router
from src.api.resume_routes import router as resume_router
from src.config import ensure_data_dirs
from src.db import init_db

FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_data_dirs()
    init_db()
    yield


app = FastAPI(title="Model Mix", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(debate_router)
app.include_router(resume_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _mount_spa() -> None:
    if not FRONTEND_DIST.is_dir():
        return
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    index = FRONTEND_DIST / "index.html"

    @app.get("/")
    async def spa_index() -> FileResponse:
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Frontend not built")
        return FileResponse(index)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        target = FRONTEND_DIST / full_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(index)


_mount_spa()

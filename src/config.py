"""Configuration: env overrides for models and data paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
UPLOADS_DIR = DATA_DIR / "uploads"
OUTPUTS_DIR = DATA_DIR / "outputs"
DB_PATH = DATA_DIR / "app.db"


@dataclass(frozen=True)
class DebaterConfig:
    """One participant in the debate (legacy panel flow)."""

    id: str
    provider: str
    model: str
    persona: str


def _debater(id: str, default_provider: str, default_model: str, persona: str) -> DebaterConfig:
    """Allow mixing providers (openai / anthropic / bedrock) via env without code edits."""
    p = os.getenv(f"DEBATER_{id.upper()}_PROVIDER", default_provider)
    m = os.getenv(f"DEBATER_{id.upper()}_MODEL", default_model)
    return DebaterConfig(id, p, m, persona)


DEBATERS: tuple[DebaterConfig, ...] = (
    _debater(
        "analyst",
        "openai",
        "gpt-4o-mini",
        "You are precise and evidence-oriented. Prefer clear structure and caveats.",
    ),
    _debater(
        "skeptic",
        "openai",
        "gpt-4o-mini",
        "You challenge assumptions, find edge cases, and demand consistency.",
    ),
    _debater(
        "pragmatist",
        "openai",
        "gpt-4o-mini",
        "You optimize for what actually helps the user act or decide today.",
    ),
)

CHAIR_PROVIDER = os.getenv("CHAIR_PROVIDER", "openai")
CHAIR_MODEL = os.getenv("CHAIR_MODEL", "gpt-4o")

# Chat mode (streaming)
CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "openai")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

# Resume pipeline stages (override without code changes)
RESUME_ANALYZE_PROVIDER = os.getenv("RESUME_ANALYZE_PROVIDER", CHAT_PROVIDER)
RESUME_ANALYZE_MODEL = os.getenv("RESUME_ANALYZE_MODEL", CHAT_MODEL)
RESUME_DRAFT_PROVIDER = os.getenv("RESUME_DRAFT_PROVIDER", CHAT_PROVIDER)
RESUME_DRAFT_MODEL = os.getenv("RESUME_DRAFT_MODEL", os.getenv("RESUME_MODEL", "gpt-4o"))
RESUME_REFINE_PROVIDER = os.getenv("RESUME_REFINE_PROVIDER", RESUME_DRAFT_PROVIDER)
RESUME_REFINE_MODEL = os.getenv("RESUME_REFINE_MODEL", RESUME_DRAFT_MODEL)


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

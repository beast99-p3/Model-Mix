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
    display_name: str
    provider: str
    model: str
    persona: str


def _env_first(keys: list[str], fallback: str) -> str:
    for k in keys:
        v = os.getenv(k)
        if v is not None and v.strip():
            return v.strip()
    return fallback


def _debater(
    *,
    id: str,
    display_name: str,
    env_key: str,
    default_provider: str,
    default_model: str,
    persona: str,
    legacy_env_keys: tuple[str, ...] = (),
) -> DebaterConfig:
    """Allow mixing providers via env while keeping backward-compatible env keys."""
    provider_keys = [f"DEBATER_{env_key}_PROVIDER", *[f"DEBATER_{k}_PROVIDER" for k in legacy_env_keys]]
    model_keys = [f"DEBATER_{env_key}_MODEL", *[f"DEBATER_{k}_MODEL" for k in legacy_env_keys]]
    p = _env_first(provider_keys, default_provider)
    m = _env_first(model_keys, default_model)
    return DebaterConfig(id=id, display_name=display_name, provider=p, model=m, persona=persona)


DEBATERS: tuple[DebaterConfig, ...] = (
    _debater(
        id="aurora",
        display_name="Aurora Lens",
        env_key="AURORA",
        default_provider="bedrock",
        default_model="deepseek.v3.2",
        persona="You are precise and evidence-oriented. Prefer clear structure and caveats.",
        legacy_env_keys=("ANALYST",),
    ),
    _debater(
        id="quartz",
        display_name="Quartz Scout",
        env_key="QUARTZ",
        default_provider="bedrock",
        default_model="google.gemma-3-12b-it",
        persona="You challenge assumptions, find edge cases, and demand consistency.",
        legacy_env_keys=("SKEPTIC",),
    ),
    _debater(
        id="nova",
        display_name="Nova Forge",
        env_key="NOVA",
        default_provider="bedrock",
        default_model="openai.gpt-oss-safeguard-120b",
        persona="You optimize for what actually helps the user act or decide today.",
        legacy_env_keys=("PRAGMATIST",),
    ),
    _debater(
        id="lyric",
        display_name="Lyric Sage",
        env_key="LYRIC",
        default_provider="bedrock",
        default_model="us.anthropic.claude-sonnet-4-6",
        persona="You are a strategic editor: improve clarity, structure, and persuasive quality.",
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
# Draft/generate uses fusion panel (DEBATER_* + CHAIR_*); RESUME_DRAFT_* kept for compatibility.
RESUME_DRAFT_PROVIDER = os.getenv("RESUME_DRAFT_PROVIDER", CHAT_PROVIDER)
RESUME_DRAFT_MODEL = os.getenv("RESUME_DRAFT_MODEL", os.getenv("RESUME_MODEL", CHAT_MODEL))
RESUME_REFINE_PROVIDER = os.getenv("RESUME_REFINE_PROVIDER", RESUME_DRAFT_PROVIDER)
RESUME_REFINE_MODEL = os.getenv("RESUME_REFINE_MODEL", RESUME_DRAFT_MODEL)


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

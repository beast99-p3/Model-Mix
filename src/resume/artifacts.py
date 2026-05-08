from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from src.config import OUTPUTS_DIR, ensure_data_dirs


@dataclass
class ArtifactMeta:
    artifact_id: str
    resume_text: str
    jd_text: str
    draft_markdown: str
    preferences: str | None = None


def new_artifact_id() -> str:
    return str(uuid.uuid4())


def artifact_paths(artifact_id: str) -> tuple[Path, Path]:
    ensure_data_dirs()
    docx = OUTPUTS_DIR / f"{artifact_id}.docx"
    meta = OUTPUTS_DIR / f"{artifact_id}.meta.json"
    return docx, meta


def write_meta(meta: ArtifactMeta) -> None:
    _, path = artifact_paths(meta.artifact_id)
    path.write_text(json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8")


def load_meta(artifact_id: str) -> ArtifactMeta:
    _, path = artifact_paths(artifact_id)
    if not path.is_file():
        raise FileNotFoundError("artifact not found")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ArtifactMeta(**raw)


def write_docx_from_markdown(artifact_id: str, markdown_text: str) -> Path:
    import re

    import docx

    docx_path, _ = artifact_paths(artifact_id)
    doc = docx.Document()
    # Split on double newlines; strip simple markdown headers for plain export
    chunks = re.split(r"\n{2,}", markdown_text.strip())
    for chunk in chunks:
        line = chunk.strip()
        line = re.sub(r"^#+\s*", "", line)
        if line:
            doc.add_paragraph(line)
    doc.save(docx_path)
    return docx_path

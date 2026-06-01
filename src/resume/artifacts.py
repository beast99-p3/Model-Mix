from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from src.config import OUTPUTS_DIR, UPLOADS_DIR, ensure_data_dirs
from src.resume.export import (
    write_docx_from_source_template,
    write_docx_from_text,
    write_pdf_from_text,
)


@dataclass
class ArtifactMeta:
    artifact_id: str
    resume_text: str
    jd_text: str
    draft_markdown: str
    preferences: str | None = None
    source_upload_id: str | None = None


def new_artifact_id() -> str:
    return str(uuid.uuid4())


def artifact_paths(artifact_id: str) -> tuple[Path, Path, Path]:
    ensure_data_dirs()
    docx = OUTPUTS_DIR / f"{artifact_id}.docx"
    pdf = OUTPUTS_DIR / f"{artifact_id}.pdf"
    meta = OUTPUTS_DIR / f"{artifact_id}.meta.json"
    return docx, pdf, meta


def save_source_upload(upload_id: str, filename: str, data: bytes) -> Path:
    """Store the user's uploaded resume for this analyze session only."""
    ensure_data_dirs()
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lower() or ".bin"
    path = UPLOADS_DIR / f"{upload_id}{ext}"
    path.write_bytes(data)
    return path


def source_upload_path(upload_id: str | None) -> Path | None:
    if not upload_id:
        return None
    matches = list(UPLOADS_DIR.glob(f"{upload_id}.*"))
    return matches[0] if matches else None


def write_meta(meta: ArtifactMeta) -> None:
    _, _, path = artifact_paths(meta.artifact_id)
    path.write_text(json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8")


def load_meta(artifact_id: str) -> ArtifactMeta:
    _, _, path = artifact_paths(artifact_id)
    if not path.is_file():
        raise FileNotFoundError("artifact not found")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ArtifactMeta(**raw)


def write_resume_exports(
    artifact_id: str,
    draft_text: str,
    *,
    source_text: str,
    source_upload_id: str | None = None,
) -> tuple[Path, Path]:
    docx_path, pdf_path, _ = artifact_paths(artifact_id)
    source_path = source_upload_path(source_upload_id)

    if source_path and source_path.suffix.lower() == ".docx":
        if write_docx_from_source_template(source_path, docx_path, draft_text, source_text):
            write_pdf_from_text(pdf_path, draft_text, source_text)
            return docx_path, pdf_path

    write_docx_from_text(docx_path, draft_text, source_text)
    write_pdf_from_text(pdf_path, draft_text, source_text)
    return docx_path, pdf_path


def write_docx_from_markdown(artifact_id: str, markdown_text: str, *, source_text: str) -> Path:
    docx_path, _ = write_resume_exports(
        artifact_id,
        markdown_text,
        source_text=source_text,
    )
    return docx_path

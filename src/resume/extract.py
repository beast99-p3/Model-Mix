from __future__ import annotations

import io
from pathlib import Path

from fastapi import UploadFile


async def read_upload_bytes(upload: UploadFile, max_bytes: int = 8_000_000) -> bytes:
    data = await upload.read()
    if len(data) > max_bytes:
        raise ValueError(f"File too large (max {max_bytes} bytes)")
    return data


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".docx"):
        return _extract_docx(data)
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    raise ValueError("Unsupported file type. Use .docx, .pdf, or .txt")


def extract_text_from_path(path: Path) -> str:
    return extract_text_from_bytes(path.name, path.read_bytes())


def _extract_docx(data: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(data))
    parts: list[str] = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            parts.append(t)
    for table in doc.tables:
        for row in table.rows:
            cells = " | ".join((c.text or "").strip() for c in row.cells if (c.text or "").strip())
            if cells:
                parts.append(cells)
    return "\n".join(parts)


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    texts: list[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        if t.strip():
            texts.append(t)
    return "\n".join(texts)

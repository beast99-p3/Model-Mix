from __future__ import annotations

import io
import re
from pathlib import Path

from fastapi import UploadFile

from src.resume.format import BULLET_PREFIX_RE, normalize_extracted_text


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
        return normalize_extracted_text(data.decode("utf-8", errors="replace"))
    raise ValueError("Unsupported file type. Use .docx, .pdf, or .txt")


def extract_text_from_path(path: Path) -> str:
    return extract_text_from_bytes(path.name, path.read_bytes())


def _paragraph_to_line(p) -> str:
    text = (p.text or "").rstrip()
    if not text:
        return ""
    style_name = (p.style.name if p.style else "") or ""
    if ("List" in style_name or "Bullet" in style_name) and not BULLET_PREFIX_RE.match(text):
        return f"• {text}"
    return text


def _extract_docx(data: bytes) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = docx.Document(io.BytesIO(data))
    parts: list[str] = []

    for child in doc.element.body.iterchildren():
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            parts.append(_paragraph_to_line(Paragraph(child, doc)))
        elif tag == "tbl":
            table = Table(child, doc)
            for row in table.rows:
                cells = " | ".join((c.text or "").strip() for c in row.cells)
                parts.append(cells)
            parts.append("")

    return normalize_extracted_text("\n".join(parts))


def _extract_pdf(data: bytes) -> str:
    try:
        import pdfplumber

        parts: list[str] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                text = page.extract_text(
                    layout=True,
                    x_tolerance=2,
                    y_tolerance=2,
                    keep_blank_chars=False,
                )
                if text and text.strip():
                    parts.append(text.rstrip())
                parts.append("")
        return normalize_extracted_text("\n".join(parts))
    except Exception:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            try:
                t = page.extract_text(extraction_mode="layout") or ""
            except TypeError:
                t = page.extract_text() or ""
            if t.strip():
                parts.append(t.rstrip())
            parts.append("")
        return normalize_extracted_text("\n".join(parts))

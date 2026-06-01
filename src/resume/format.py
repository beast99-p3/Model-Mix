from __future__ import annotations

import re
from typing import Literal

BULLET_PREFIX_RE = re.compile(
    r"^(\s*)([-–—•*·◦▪●○]\s+|\d+[.)]\s+)",
)

META_LINE_RE = re.compile(
    r"(?i)^(?:"
    r"we need to|so we need|thus we|let['']s |but our |now (?:check|count|maybe)|maybe we |"
    r"actually the|the requirement|output must|output only|line count|exactly \d+ lines|"
    r"what i changed|improved resume|internal process|the user asked|our edited version|"
    r"original source|final answer|count lines|that['']s \d+ lines|something off|"
    r"possibly the|the easiest is|we['']ll start|i['']ll copy|let['']s count|let['']s re-?write|"
    r"let['']s double-check|don['']t include|cannot include|should not|must not include|"
    r"no extra commentary|presumably \d+ lines|our version|our current count|"
    r"thus final|good\.|well\.|note that|important:|reminder:"
    r")",
)

LINE_ANNOTATION_RE = re.compile(r"^[\•\-\*]?\s*Line\s*\d+\s*:", re.I)

LineRole = Literal["blank", "name", "contact", "heading", "bullet", "continuation", "body"]


def split_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def is_blank_line(line: str) -> bool:
    return not line.strip()


def bullet_parts(line: str) -> tuple[str, str]:
    m = BULLET_PREFIX_RE.match(line)
    if not m:
        lead = line[: len(line) - len(line.lstrip())]
        return lead, line.strip()
    return m.group(1) + m.group(2), line[m.end() :].strip()


def strip_bullet_content(line: str) -> str:
    return bullet_parts(line)[1]


def normalize_text_chars(text: str) -> str:
    replacements = {
        "\u25a0": "-",
        "\u25aa": "-",
        "\u25a1": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00ad": "",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufffd": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"(\w)■(\w)", r"\1-\2", text)
    text = re.sub(r"(\w)-\s+(\w)", r"\1-\2", text)
    return text


def normalize_extracted_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = normalize_text_chars(text)
    text = re.sub(r"(\w)-\n(\w)", r"\1-\2", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def is_section_heading(line: str) -> bool:
    s = line.strip()
    if len(s) < 3 or len(s) > 55:
        return False
    letters = re.sub(r"[^A-Za-z ]", "", s)
    if len(letters) < 3:
        return False
    if len(s.split()) > 7:
        return False
    return s.upper() == s


def is_contact_line(line: str) -> bool:
    s = line.strip()
    return ("@" in s or "|" in s) and any(ch.isdigit() for ch in s)


def line_role(source_lines: list[str], index: int) -> LineRole:
    line = source_lines[index]
    if is_blank_line(line):
        return "blank"
    stripped = line.strip()
    if index == 0:
        return "name"
    if index == 1 and is_contact_line(line):
        return "contact"
    if is_section_heading(stripped):
        return "heading"
    if bullet_parts(line)[0].strip():
        return "bullet"
    indent = len(line) - len(line.lstrip())
    if indent >= 4 and index > 0:
        prev = source_lines[index - 1]
        if prev.strip() and not is_section_heading(prev.strip()):
            return "continuation"
    if is_contact_line(line):
        return "contact"
    return "body"


def _is_meta_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if META_LINE_RE.search(stripped):
        return True
    if LINE_ANNOTATION_RE.match(stripped):
        return True
    if re.search(r"(?i)\bline\s*\d+\s*:", stripped) and len(stripped) < 120:
        return True
    return False


def _extract_improved_resume_block(text: str) -> str:
    patterns = [
        r"(?is)(?:^|\n)2\)\s*[\"']?Improved resume[\"']?\s*\n",
        r"(?is)(?:^|\n)[\"']?Improved resume[\"']?\s*:?\s*\n",
        r"(?is)(?:^|\n)##?\s*Improved resume\s*\n",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return text[m.end() :].strip()
    return text


def clean_fusion_resume_output(generated: str, source: str) -> str:
    text = normalize_text_chars(generated.strip())
    text = re.sub(r"^```(?:\w+)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(
        r"(?is)^1\)\s*[\"']?What I changed[\"']?\s*\n.*?(?=\n2\)\s|[\"']?Improved resume|\Z)",
        "",
        text,
    )
    text = normalize_text_chars(_extract_improved_resume_block(text))

    src_lines = [line for line in split_lines(source) if line.strip()]
    if src_lines:
        anchor = src_lines[0].strip()
        pos = text.find(anchor)
        if pos > 0:
            prefix_lines = [l for l in split_lines(text[:pos]) if l.strip()]
            if len(prefix_lines) >= 2 or any(_is_meta_line(l) for l in prefix_lines):
                text = text[pos:].strip()

    kept: list[str] = []
    for line in split_lines(text):
        if _is_meta_line(line):
            continue
        kept.append(normalize_text_chars(line.rstrip()))

    text = "\n".join(kept).strip()
    non_blank = sum(1 for line in split_lines(text) if line.strip())
    src_non_blank = sum(1 for line in split_lines(source) if line.strip())
    if non_blank < 3 or (src_non_blank > 0 and non_blank < src_non_blank * 0.35):
        return normalize_text_chars(source)
    return text


def _merge_line_content(source_line: str, generated_line: str) -> str:
    if is_blank_line(generated_line):
        return source_line.rstrip()
    sp, _ = bullet_parts(source_line)
    _, gc = bullet_parts(generated_line)
    content = gc if gc else generated_line.strip()
    content = normalize_text_chars(content)
    if sp.strip():
        return f"{sp}{content}".rstrip()
    lead = source_line[: len(source_line) - len(source_line.lstrip())]
    return f"{lead}{content}".rstrip()


def apply_source_layout(source: str, generated: str) -> str:
    """Map generated content onto the user's source resume line skeleton exactly."""
    src_lines = split_lines(normalize_text_chars(source))
    gen_lines = split_lines(normalize_text_chars(generated))

    if len(gen_lines) == len(src_lines):
        return "\n".join(
            "" if is_blank_line(sl) else _merge_line_content(sl, gl)
            for sl, gl in zip(src_lines, gen_lines)
        )

    gen_content = [strip_bullet_content(line) for line in gen_lines if line.strip()]
    out: list[str] = []
    gi = 0
    for sl in src_lines:
        if is_blank_line(sl):
            out.append("")
            continue
        prefix, _ = bullet_parts(sl)
        if gi < len(gen_content):
            content = normalize_text_chars(gen_content[gi])
            if prefix.strip():
                out.append(f"{prefix}{content}".rstrip())
            else:
                lead = sl[: len(sl) - len(sl.lstrip())]
                out.append(f"{lead}{content}".rstrip())
            gi += 1
        else:
            out.append(sl.rstrip())
    return "\n".join(out)


def finalize_resume_output(source: str, raw: str) -> str:
    source = normalize_text_chars(source)
    cleaned = clean_fusion_resume_output(raw, source)
    aligned = apply_source_layout(source, cleaned)
    return normalize_text_chars(aligned)


def sanitize_panel_turn(text: str) -> str:
    return clean_fusion_resume_output(text, "")


def line_count(text: str) -> int:
    return len(split_lines(text))

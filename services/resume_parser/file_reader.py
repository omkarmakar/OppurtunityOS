"""Read text content from PDF and DOCX files."""

from __future__ import annotations

from pathlib import Path

import docx
from pypdf import PdfReader


def read_pdf(path: str | Path) -> str:
    reader = PdfReader(path)
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            lines.append(text)
    return "\n".join(lines)


def read_docx(path: str | Path) -> str:
    doc = docx.Document(path)
    lines: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            lines.append(para.text)
    return "\n".join(lines)


def read_resume_file(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    elif suffix == ".docx":
        return read_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .pdf or .docx")

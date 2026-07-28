"""Read text content from PDF, DOCX, and LaTeX files."""

from __future__ import annotations

from pathlib import Path

import docx
from pypdf import PdfReader

try:
    from pylatexenc.latex2text import LatexNodes2Text
    LATEX_SUPPORT = True
except ImportError:
    LATEX_SUPPORT = False
    LatexNodes2Text = None


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


def read_tex(path: str | Path) -> str:
    if not LATEX_SUPPORT:
        raise ImportError(
            "LaTeX support requires 'pylatexenc'. "
            "Install with: pip install pylatexenc"
        )
    raw = Path(path).read_text(encoding="utf-8")
    converter = LatexNodes2Text()
    return converter.latex_to_text(raw)


def read_resume_file(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    elif suffix == ".docx":
        return read_docx(path)
    elif suffix == ".tex":
        return read_tex(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .pdf, .docx, or .tex")

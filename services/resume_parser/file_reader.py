"""Extract raw text from resume file formats (PDF, DOCX, TeX)."""

from __future__ import annotations

import re
from pathlib import Path


def _clean(text: str) -> str:
    """Collapse excessive whitespace while preserving line breaks."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_pdf(path: Path) -> str:
    """Extract text from a PDF using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return _clean("\n\n".join(pages))


def read_docx(path: Path) -> str:
    """Extract text from a DOCX using python-docx."""
    from docx import Document

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs]
    return _clean("\n".join(paragraphs))


def read_tex(path: Path) -> str:
    """Strip LaTeX commands from a .tex file and return plain text."""
    raw = path.read_text(encoding="utf-8", errors="replace")

    # Remove comments (% to end of line)
    raw = re.sub(r"(?m)%.*$", "", raw)

    # Remove common environments that produce no visible text
    raw = re.sub(r"\\begin\{(comment|lstlisting|verbatim)\}.*?\\end\{\1\}", "", raw, flags=re.DOTALL)

    # Replace common commands with their text content
    replacements = {
        r"\\textbf\{([^}]*)\}": r"\1",
        r"\\textit\{([^}]*)\}": r"\1",
        r"\\emph\{([^}]*)\}": r"\1",
        r"\\text\{([^}]*)\}": r"\1",
        r"\\texttt\{([^}]*)\}": r"\1",
        r"\\href\{[^}]*\}\{([^}]*)\}": r"\1",
        r"\\url\{([^}]*)\}": r"\1",
        r"\\item\s*": "• ",
        r"\\\\": "\n",
        r"\\&": "&",
        r"\\%": "%",
        r"\\#": "#",
        r"\\(\[|\])": "",
        r"\\section\*?\{([^}]*)\}": r"\n\1\n",
        r"\\subsection\*?\{([^}]*)\}": r"\n\1\n",
        r"\\subsubsection\*?\{([^}]*)\}": r"\n\1\n",
        r"\\paragraph\*?\{([^}]*)\}": r"\n\1\n",
        r"\\begin\{(itemize|enumerate|description)\}": "",
        r"\\end\{(itemize|enumerate|description)\}": "",
        r"\\begin\{document\}": "",
        r"\\end\{document\}": "",
    }
    for pattern, repl in replacements.items():
        raw = re.sub(pattern, repl, raw)

    # Strip remaining simple commands like \vspace, \smallskip, etc.
    raw = re.sub(r"\\(vspace|smallskip|medskip|bigskip|clearpage|newpage|noindent|centering)\b(\[[^\]]*\])?", "", raw)
    # Remove any remaining \command{...} by extracting the content
    raw = re.sub(r"\\[a-zA-Z]+\*?\{([^{}]*)\}", r"\1", raw)
    # Remove standalone commands
    raw = re.sub(r"\\[a-zA-Z]+\*?", "", raw)

    # Remove braces
    raw = raw.replace("{", "").replace("}", "")

    return _clean(raw)


def read_resume_file(path: Path) -> str:
    """Dispatch to the correct reader based on file extension."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    elif suffix == ".docx":
        return read_docx(path)
    elif suffix == ".tex":
        return read_tex(path)
    else:
        raise ValueError(f"Unsupported resume file type: {suffix}")

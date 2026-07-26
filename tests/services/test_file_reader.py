"""Tests for resume file_reader module."""

from __future__ import annotations

import os
import tempfile
import uuid

import pytest

from services.resume_parser.file_reader import read_resume_file, read_tex

SAMPLE_TEX_SKILLS = r"""\documentclass{article}
\begin{document}
\section{Skills}
Python, Java, C++
\end{document}
"""

SAMPLE_TEX_FULL = r"""\documentclass{article}
\usepackage{geometry}
\begin{document}

\section{Skills}
Python, Java, \textbf{Deep Learning}

\section{Experience}
Senior Developer at Acme
2020 -- 2024
\begin{itemize}
    \item Built APIs with FastAPI
\end{itemize}

\section{Education}
MIT
2014 -- 2018
B.S. in Computer Science

\end{document}
"""


class TestReadTex:
    def test_read_tex_returns_plain_text(self) -> None:
        path = os.path.join(tempfile.gettempdir(), f"test_{uuid.uuid4().hex}.tex")
        with open(path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_TEX_SKILLS)
        try:
            text = read_tex(path)
            assert "Skills" in text
            assert "Python" in text
            assert "Java" in text
            assert "C++" in text
        finally:
            os.unlink(path)

    def test_read_tex_strips_latex_commands(self) -> None:
        path = os.path.join(tempfile.gettempdir(), f"test_{uuid.uuid4().hex}.tex")
        with open(path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_TEX_FULL)
        try:
            text = read_tex(path)
            # Section headers should be extracted as plain text
            assert "Skills" in text
            assert "Experience" in text
            assert "Education" in text
            # \textbf should be stripped, leaving the text inside
            assert "Deep Learning" in text
            # Preamble commands should not appear
            assert "documentclass" not in text.lower()
            assert "usepackage" not in text.lower()
        finally:
            os.unlink(path)


class TestReadResumeFile:
    def test_read_resume_file_tex(self) -> None:
        path = os.path.join(tempfile.gettempdir(), f"test_{uuid.uuid4().hex}.tex")
        with open(path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_TEX_SKILLS)
        try:
            text = read_resume_file(path)
            assert "Python" in text
        finally:
            os.unlink(path)

    def test_read_resume_file_unsupported_raises(self) -> None:
        path = os.path.join(tempfile.gettempdir(), f"test_{uuid.uuid4().hex}.xyz")
        with open(path, "w") as f:
            f.write("not a resume")
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                read_resume_file(path)
        finally:
            os.unlink(path)

    def test_read_resume_file_missing_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_resume_file("/nonexistent/path/file.pdf")

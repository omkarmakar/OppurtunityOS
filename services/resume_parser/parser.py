"""Deterministic resume parser — section-based extraction without AI."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParseResult:
    skills: list[str] = field(default_factory=list)
    projects: list[dict[str, str]] = field(default_factory=list)
    education: list[dict[str, str]] = field(default_factory=list)
    experience: list[dict[str, str]] = field(default_factory=list)


SECTION_HEADERS: dict[str, list[str]] = {
    "education": [
        "education", "educational background", "academic background",
        "academic history", "qualifications",
    ],
    "experience": [
        "experience", "work experience", "employment", "work history",
        "professional experience", "career history",
    ],
    "skills": [
        "skills", "technical skills", "core competencies", "expertise",
        "technologies", "competencies", "proficiencies",
        "technical expertise", "key skills",
    ],
    "projects": [
        "projects", "project experience", "personal projects",
        "key projects", "technical projects", "project work",
    ],
}


def _normalize_header(line: str) -> str:
    cleaned = re.sub(r"^[#*\-•·\d.]+", "", line).strip().rstrip(":").strip().lower()
    return cleaned


def _detect_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        normalized = _normalize_header(stripped)
        matched_section: str | None = None
        for section_name, keywords in SECTION_HEADERS.items():
            if normalized in keywords or any(
                kw in normalized for kw in keywords
            ):
                matched_section = section_name
                break

        if matched_section:
            current_section = matched_section
            sections.setdefault(current_section, [])
        elif current_section:
            sections[current_section].append(stripped)

    return sections


_DATE_PATTERN = re.compile(
    r"(\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"(?:uary|ruary|ch|il|e|ly|ust|tember|ober|ember|)?"
    r"\.?\s*\d{4}\b|\b\d{4}\b)"
    r"\s*(?:[-–—to]+|present|current)\s*"
    r"(\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"(?:uary|ruary|ch|il|e|ly|ust|tember|ober|ember|)?"
    r"\.?\s*\d{4}\b|\b\d{4}\b|present|current)",
    re.IGNORECASE,
)


def _has_date(line: str) -> bool:
    return bool(_DATE_PATTERN.search(line)) or bool(
        re.search(r"\b\d{4}\b", line)
    )


def _parse_education(lines: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in lines:
        if _has_date(line):
            if current:
                entries.append(current)
            current = {"institution": "", "degree": "", "field": "", "start_date": "", "end_date": ""}
            dates = re.findall(r"\b\d{4}\b", line)
            if len(dates) >= 2:
                current["start_date"] = dates[0]
                current["end_date"] = dates[1]
            elif len(dates) == 1:
                current["end_date"] = dates[0]
            rest = _DATE_PATTERN.sub("", line).strip().rstrip("-–—,").strip()
            if rest:
                current["institution"] = rest
        elif current:
            if not current.get("institution"):
                current["institution"] = line
            elif not current.get("degree"):
                current["degree"] = line
            elif not current.get("field"):
                current["field"] = line
            else:
                current.setdefault("institution", "")
                current["institution"] += " " + line
    if current:
        entries.append(current)
    return entries


def _parse_experience(lines: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in lines:
        if _has_date(line):
            if current:
                entries.append(current)
            current = {"company": "", "role": "", "description": "", "start_date": "", "end_date": ""}
            dates = re.findall(r"\b\d{4}\b", line)
            if len(dates) >= 2:
                current["start_date"] = dates[0]
                current["end_date"] = dates[1]
            elif len(dates) == 1:
                current["end_date"] = dates[0]
            rest = _DATE_PATTERN.sub("", line).strip().rstrip("-–—,").strip()
            if rest:
                current["role"] = rest
        elif current:
            if not current.get("role"):
                current["role"] = line
            elif not current.get("company"):
                current["company"] = line
            elif line.startswith(("-", "•", "*", "·")):
                desc = current.setdefault("description", "")
                if desc:
                    desc += " "
                current["description"] = desc + line.lstrip("-•*· ").strip()
            else:
                current["company"] = line
    if current:
        entries.append(current)
    return entries


def _parse_projects(lines: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in lines:
        if not current or _has_date(line) or (line.isupper() and len(line) > 3):
            if current:
                entries.append(current)
            current = {"name": "", "description": "", "technologies": "", "url": ""}
            current["name"] = line.strip(":").strip()
        elif current:
            if line.startswith(("-", "•", "*", "·")):
                desc = current.setdefault("description", "")
                if desc:
                    desc += " "
                current["description"] = desc + line.lstrip("-•*· ").strip()
            elif re.search(r"github|gitlab|bitbucket|\.com", line, re.IGNORECASE):
                current["url"] = line.strip()
            else:
                tech = current.setdefault("technologies", "")
                if tech:
                    tech += ", "
                current["technologies"] = tech + line.strip()
    if current:
        entries.append(current)
    return entries


def _parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in lines:
        parts = re.split(r"[,;|•\n]", line)
        for part in parts:
            cleaned = part.strip().lstrip("-* ").strip()
            if cleaned and len(cleaned) > 1:
                skills.append(cleaned)
    seen: list[str] = []
    for s in skills:
        low = s.lower()
        if low not in [x.lower() for x in seen]:
            seen.append(s)
    return seen


class ResumeParser:
    """Deterministic resume parser using section headers and patterns."""

    def parse(self, text: str) -> ParseResult:
        lines = text.split("\n")
        sections = _detect_sections(lines)

        result = ParseResult()

        if "skills" in sections:
            result.skills = _parse_skills(sections["skills"])

        if "projects" in sections:
            result.projects = _parse_projects(sections["projects"])

        if "education" in sections:
            result.education = _parse_education(sections["education"])

        if "experience" in sections:
            result.experience = _parse_experience(sections["experience"])

        return result

"""Resume parsing + save endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.schemas.profiles import (
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    ProfileResponse,
    ResumeParseResponse,
)
from database.models import Profile
from database.repositories import ProfileRepository
from services.resume_parser import read_resume_file
from services.resume_parser.parser import ResumeParser

router = APIRouter()
_parser = ResumeParser()
UPLOAD_DIR = Path("data/resumes")


async def _parse_file(file: UploadFile) -> tuple[str, ResumeParseResponse, Path, str]:
    """Core file parsing logic shared by parse-only and parse-and-save endpoints.

    Returns (raw_text, parse_response, saved_dest, original_filename).
    """
    if file.filename is None:
        raise HTTPException(status_code=400, detail="No filename provided")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".tex"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Use .pdf, .docx, or .tex",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"

    content = await file.read()
    dest.write_bytes(content)

    text = read_resume_file(dest)
    result = _parser.parse(text)

    parse_resp = ResumeParseResponse(
        skills=result.skills,
        projects=[
            ProjectEntry(
                name=p.get("name", ""),
                description=p.get("description", ""),
                technologies=p.get("technologies", ""),
                url=p.get("url", ""),
            )
            for p in result.projects
        ],
        education=[
            EducationEntry(
                institution=e.get("institution", ""),
                degree=e.get("degree", ""),
                field=e.get("field", ""),
                start_date=e.get("start_date", ""),
                end_date=e.get("end_date", ""),
            )
            for e in result.education
        ],
        experience=[
            ExperienceEntry(
                company=e.get("company", ""),
                role=e.get("role", ""),
                description=e.get("description", ""),
                start_date=e.get("start_date", ""),
                end_date=e.get("end_date", ""),
            )
            for e in result.experience
        ],
        file_name=file.filename or "",
    )

    return text, parse_resp, dest, file.filename


@router.post("/resume/parse", response_model=ResumeParseResponse)
async def parse_resume(file: UploadFile) -> ResumeParseResponse:
    """Parse a resume file and return structured data without saving to a profile."""
    _, parse_resp, dest, _ = await _parse_file(file)
    if dest.exists():
        dest.unlink()
    return parse_resp


@router.post("/resume/parse-and-save/{user_id}", response_model=ProfileResponse)
async def parse_and_save(
    user_id: uuid.UUID, file: UploadFile, db: Session = Depends(get_db),
) -> ProfileResponse:
    """Parse and save resume data into the user's first profile (permanent file storage)."""
    raw_text, parse_resp, dest, original_name = await _parse_file(file)

    repo = ProfileRepository(db)
    profile = repo.get_by_user_id(user_id)
    if not profile:
        if dest.exists():
            dest.unlink()
        raise HTTPException(status_code=404, detail="Profile not found. Create profile first.")

    update_data: dict[str, Any] = {
        "raw_extracted_text": raw_text,
        "resume_filename": original_name,
        "resume_uploaded_at": datetime.now(timezone.utc),
    }
    if parse_resp.skills:
        update_data["skills"] = parse_resp.skills
    if parse_resp.education:
        update_data["education"] = [e.model_dump() for e in parse_resp.education]
    if parse_resp.experience:
        update_data["experience"] = [e.model_dump() for e in parse_resp.experience]
    if parse_resp.projects:
        update_data["projects"] = [p.model_dump() for p in parse_resp.projects]

    for key, value in update_data.items():
        setattr(profile, key, value)
    repo.update(profile)
    db.commit()
    db.refresh(profile)

    return ProfileResponse.model_validate(profile)

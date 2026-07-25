"""Resume parsing endpoint."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.schemas.profiles import (
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    ProfileResponse,
    ProfileUpdate,
    ResumeParseResponse,
)
from database.models import Profile
from database.repositories import ProfileRepository
from services.resume_parser import read_resume_file
from services.resume_parser.parser import ResumeParser

router = APIRouter()
_parser = ResumeParser()
UPLOAD_DIR = Path("data/resumes")


@router.post("/resume/parse", response_model=ResumeParseResponse)
async def parse_resume(file: UploadFile) -> ResumeParseResponse:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="No filename provided")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Use .pdf or .docx",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"
    try:
        content = await file.read()
        dest.write_bytes(content)

        text = read_resume_file(dest)
        result = _parser.parse(text)

        return ResumeParseResponse(
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
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse resume: {e}")
    finally:
        if dest.exists():
            dest.unlink()


@router.post("/resume/parse-and-save/{user_id}", response_model=ProfileResponse)
async def parse_and_save(
    user_id: uuid.UUID, file: UploadFile, db: Session = Depends(get_db),
) -> ProfileResponse:
    parse_resp = await parse_resume(file)
    repo = ProfileRepository(db)
    profile = repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Create profile first.")

    update_data: dict = {}
    if parse_resp.skills:
        update_data["skills"] = parse_resp.skills
    if parse_resp.education:
        update_data["education"] = [e.model_dump() for e in parse_resp.education]
    if parse_resp.experience:
        update_data["experience"] = [e.model_dump() for e in parse_resp.experience]
    if parse_resp.projects:
        update_data["projects"] = [p.model_dump() for p in parse_resp.projects]

    if update_data:
        for key, value in update_data.items():
            setattr(profile, key, value)
        repo.update(profile)
        db.commit()
        db.refresh(profile)

    return ProfileResponse.model_validate(profile)

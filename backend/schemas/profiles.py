"""Profile CRUD schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EducationEntry(BaseModel):
    institution: str = Field(default="", description="School or university name")
    degree: str = Field(default="", description="Degree earned")
    field: str = Field(default="", description="Field of study")
    start_date: str = Field(default="", description="Start date (YYYY-MM)")
    end_date: str = Field(default="", description="End date (YYYY-MM or present)")


class ExperienceEntry(BaseModel):
    company: str = Field(default="", description="Company name")
    role: str = Field(default="", description="Job title")
    description: str = Field(default="", description="Role description")
    start_date: str = Field(default="", description="Start date (YYYY-MM)")
    end_date: str = Field(default="", description="End date (YYYY-MM or present)")


class ProjectEntry(BaseModel):
    name: str = Field(default="", description="Project name")
    description: str = Field(default="", description="Project description")
    technologies: str = Field(default="", description="Technologies used")
    url: str = Field(default="", description="Project URL")


class ResumeParseResponse(BaseModel):
    skills: list[str] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    file_name: str = Field(default="", description="Source filename")


class ProfileCreate(BaseModel):
    user_id: UUID = Field(description="User ID")
    display_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None)
    education: list[EducationEntry] | None = Field(default=None)
    experience: list[ExperienceEntry] | None = Field(default=None)
    skills: list[str] | None = Field(default=None)
    preferred_locations: list[str] | None = Field(default=None)
    salary_expectations: str | None = Field(default=None, max_length=200)
    target_companies: list[str] | None = Field(default=None)
    keywords: list[str] | None = Field(default=None)
    resume_path: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio: str | None = Field(default=None, max_length=500)
    projects: list[ProjectEntry] | None = Field(default=None)


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None)
    education: list[EducationEntry] | None = Field(default=None)
    experience: list[ExperienceEntry] | None = Field(default=None)
    skills: list[str] | None = Field(default=None)
    preferred_locations: list[str] | None = Field(default=None)
    salary_expectations: str | None = Field(default=None, max_length=200)
    target_companies: list[str] | None = Field(default=None)
    keywords: list[str] | None = Field(default=None)
    resume_path: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio: str | None = Field(default=None, max_length=500)
    projects: list[ProjectEntry] | None = Field(default=None)


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str | None
    avatar_url: str | None
    bio: str | None
    education: list[EducationEntry] | None
    experience: list[ExperienceEntry] | None
    skills: list[str] | None
    preferred_locations: list[str] | None
    salary_expectations: str | None
    target_companies: list[str] | None
    keywords: list[str] | None
    resume_path: str | None
    linkedin_url: str | None
    github_url: str | None
    portfolio: str | None
    projects: list[ProjectEntry] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

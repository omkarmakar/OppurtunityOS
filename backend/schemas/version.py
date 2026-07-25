"""Version response schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VersionResponse(BaseModel):
    name: str = Field(default="opportunityos", description="Application name")
    version: str = Field(description="Application version")
    python: str = Field(description="Python runtime version")

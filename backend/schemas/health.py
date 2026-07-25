"""Health check response schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Application health status")
    database: str = Field(default="connected", description="Database connectivity status")

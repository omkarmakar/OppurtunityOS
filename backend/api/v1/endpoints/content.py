"""Content extraction endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from services.content_extractor import ContentExtractor

router = APIRouter()
_extractor = ContentExtractor()


class ExtractRequest(BaseModel):
    url: str = Field(description="URL to extract content from")


class ExtractResponse(BaseModel):
    title: str = Field(default="", description="Page title")
    content: str = Field(default="", description="Clean text content")
    date: str = Field(default="", description="Extracted date")
    author: str = Field(default="", description="Extracted author")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    source_url: str = Field(default="", description="Original URL")


@router.post("/content/extract", response_model=ExtractResponse)
async def extract_content(req: ExtractRequest) -> ExtractResponse:
    try:
        result = await _extractor.extract(req.url)
        return ExtractResponse(
            title=result.title,
            content=result.content,
            date=result.date,
            author=result.author,
            metadata=result.metadata,
            source_url=result.source_url,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Extraction failed: {e}")

"""Search provider listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from services.search.registry import SearchRegistry

router = APIRouter()


class SearchProviderInfo(BaseModel):
    name: str


@router.get("/search-providers", response_model=list[SearchProviderInfo])
async def list_search_providers() -> list[SearchProviderInfo]:
    registry = SearchRegistry.default()
    return [SearchProviderInfo(name=n) for n in sorted(registry.list())]

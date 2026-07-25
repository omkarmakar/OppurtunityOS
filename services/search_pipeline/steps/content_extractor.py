"""Pipeline step — extracts clean text from search result URLs."""

from __future__ import annotations

import logging
from typing import Any

from services.content_extractor import ContentExtractor, ExtractedContent
from services.search.models import SearchResult
from services.search_pipeline.steps.base import PipelineStep

logger = logging.getLogger(__name__)


class ContentExtractorStep(PipelineStep):
    def __init__(self, timeout: int = 30) -> None:
        self._extractor = ContentExtractor(timeout=timeout)

    @property
    def name(self) -> str:
        return "ContentExtractor"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        results: list[SearchResult] = ctx.get("search_results", [])
        if not results:
            ctx["extracted_contents"] = []
            return ctx

        extracted: list[dict[str, Any]] = []

        for result in results:
            if not result.url:
                continue
            try:
                content: ExtractedContent = await self._extractor.extract(result.url)
                extracted.append({
                    "search_result": result,
                    "content": content,
                })
            except Exception as exc:
                logger.warning("Content extraction failed for %s: %s", result.url, exc)
                extracted.append({
                    "search_result": result,
                    "content": ExtractedContent(source_url=result.url),
                })

        ctx["extracted_contents"] = extracted
        return ctx

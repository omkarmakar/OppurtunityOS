"""Pipeline step — extracts clean text from search result URLs."""

from __future__ import annotations

import logging
from typing import Any

from services.content_extractor import ContentExtractor, ExtractedContent
from services.search.models import SearchResult
from services.search_pipeline.filters import is_quality_job_url
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
        filtered_out = 0

        for result in results:
            if not result.url:
                continue

            # Filter out junk URLs (listing pages, Q&A, advice sites)
            if not is_quality_job_url(result.url, result.title):
                filtered_out += 1
                logger.debug("Filtered junk URL: %s (%s)", result.url, result.title)
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

        if filtered_out:
            logger.info("ContentExtractor: filtered %d junk URLs, %d remaining", filtered_out, len(extracted))

        ctx["extracted_contents"] = extracted
        return ctx

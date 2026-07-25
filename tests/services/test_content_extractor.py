"""Content extractor tests."""

from __future__ import annotations

import os

import pytest

from services.content_extractor import ContentExtractor, ExtractedContent


class TestExtractedContent:
    def test_default_fields(self) -> None:
        ec = ExtractedContent()
        assert ec.title == ""
        assert ec.content == ""
        assert ec.date == ""
        assert ec.author == ""
        assert ec.metadata == {}
        assert ec.source_url == ""

    def test_all_fields(self) -> None:
        ec = ExtractedContent(
            title="T", content="C", date="2024-01-01",
            author="A", metadata={"key": "val"}, source_url="https://example.com",
        )
        assert ec.title == "T"
        assert ec.metadata["key"] == "val"


class TestContentExtractor:
    @pytest.mark.asyncio
    async def test_extract_html_page(self) -> None:
        extractor = ContentExtractor()
        result = await extractor.extract("https://example.com")
        assert isinstance(result, ExtractedContent)
        assert result.source_url == "https://example.com"
        assert "status_code" in result.metadata

    @pytest.mark.asyncio
    async def test_extract_returns_metadata(self) -> None:
        extractor = ContentExtractor()
        result = await extractor.extract("https://example.com")
        assert isinstance(result.metadata, dict)

    @pytest.mark.asyncio
    async def test_extract_invalid_url_raises(self) -> None:
        extractor = ContentExtractor(timeout=5)
        with pytest.raises(Exception):
            await extractor.extract("https://nonexistent-domain-xyz789.com/page")

    @pytest.mark.asyncio
    async def test_extract_pdf_url(self) -> None:
        extractor = ContentExtractor()
        with pytest.raises(Exception):
            await extractor.extract("https://example.com/doc.pdf")

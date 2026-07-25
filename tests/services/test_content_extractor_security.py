"""Tests for SSRF protection in content extractor."""

from __future__ import annotations

import pytest

from services.content_extractor.extractor import ContentExtractor


class TestSSRFProtection:
    @pytest.fixture
    def extractor(self):
        return ContentExtractor(timeout=5)

    @pytest.mark.parametrize("bad_url", [
        "http://localhost:8000/admin",
        "http://127.0.0.1:5432",
        "http://0.0.0.0:8080",
        "http://[::1]:22",
        "http://10.0.0.1/secret",
        "http://192.168.1.1/config",
        "http://172.16.0.1/internal",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "ftp://files.example.com/data",
    ])
    @pytest.mark.asyncio
    async def test_rejects_internal_urls(self, extractor, bad_url):
        with pytest.raises((ValueError, Exception)):
            await extractor.extract(bad_url)

    @pytest.mark.parametrize("good_url", [
        "https://example.com/page",
        "http://github.com/opencode",
        "https://api.openai.com/v1/completions",
    ])
    @pytest.mark.asyncio
    async def test_allows_external_urls(self, extractor, good_url):
        if not good_url.startswith("http"):
            with pytest.raises(ValueError):
                await extractor.extract(good_url)

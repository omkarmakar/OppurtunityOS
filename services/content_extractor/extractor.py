"""Content extraction — downloads and extracts clean text from URLs and PDFs."""

from __future__ import annotations

import io
import ipaddress
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import trafilatura
from pypdf import PdfReader


@dataclass
class ExtractedContent:
    title: str = ""
    content: str = ""
    date: str = ""
    author: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    source_url: str = ""


class ContentExtractor:
    """Extracts clean text content from web pages and PDF URLs."""

    # Private/reserved IP ranges to block for SSRF prevention.
    _BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
        ipaddress.ip_network(n)
        for n in [
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "127.0.0.0/8",
            "169.254.0.0/16",
            "::1/128",
            "fc00::/7",
            "fe80::/10",
        ]
    ]

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    async def extract(self, url: str) -> ExtractedContent:
        self._validate_url(url)
        result = ExtractedContent(source_url=url)

        if url.lower().endswith(".pdf"):
            text = await self._fetch_pdf(url)
            result.content = text
            return result

        return await self._extract_html(url, result)

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
        hostname = parsed.hostname or ""
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]"):
            raise ValueError(f"Blocked internal URL: {url}")
        try:
            ip = ipaddress.ip_address(hostname)
            for net in ContentExtractor._BLOCKED_NETWORKS:
                if ip in net:
                    raise ValueError(f"Blocked private/reserved IP: {url}")
        except ValueError:
            if any(hostname.endswith(s) for s in (".local", ".internal", ".lan")):
                raise ValueError(f"Blocked internal hostname: {url}")

    async def _fetch_pdf(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            reader = PdfReader(io.BytesIO(resp.content))
            pages: list[str] = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n".join(pages)

    async def _extract_html(self, url: str, result: ExtractedContent) -> ExtractedContent:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text

        result.metadata["status_code"] = resp.status_code
        result.metadata["content_type"] = resp.headers.get("content-type", "")

        extracted = await self._run_trafilatura(html, url)
        if extracted:
            result.title = extracted.get("title", "")
            result.content = extracted.get("text", "")
            result.date = extracted.get("date", "")
            result.author = extracted.get("author", "")
            for key, value in extracted.items():
                if key not in ("title", "text", "date", "author"):
                    result.metadata[key] = value

        return result

    async def _run_trafilatura(self, html: str, url: str) -> dict[str, Any] | None:
        extracted = trafilatura.bare_extraction(
            html,
            url=url,
            include_links=False,
            include_images=False,
            include_tables=False,
            no_fallback=False,
            favor_recall=False,
        )
        if extracted is None:
            return None
        if isinstance(extracted, dict):
            return extracted
        return None

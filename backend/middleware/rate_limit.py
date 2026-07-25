"""In-memory sliding-window rate limiter middleware."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter per client IP.

    Applies per-route limits.  Exempts health/version endpoints.
    """

    def __init__(
        self,
        app: ASGIApp,
        default_limit: int = 60,
        window_seconds: int = 60,
        route_limits: dict[str, int] | None = None,
    ) -> None:
        super().__init__(app)
        self._default_limit = default_limit
        self._window_seconds = window_seconds
        self._route_limits = route_limits or {}
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._cleanup_interval = 300.0
        self._last_cleanup = time.monotonic()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method == "GET" and request.url.path in ("/api/v1/health", "/api/v1/version"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        limit = self._default_limit
        for prefix, lmt in self._route_limits.items():
            if request.url.path.startswith(prefix):
                limit = lmt
                break

        now = time.monotonic()
        bucket = self._buckets[client_ip]

        # purge expired entries
        cutoff = now - self._window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)

        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(int(self._window_seconds))},
            )

        bucket.append(now)

        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup()

        return await call_next(request)

    def _cleanup(self) -> None:
        cutoff = time.monotonic() - self._window_seconds
        self._buckets = {
            ip: times
            for ip, times in self._buckets.items()
            if any(t > cutoff for t in times)
        }
        self._last_cleanup = time.monotonic()

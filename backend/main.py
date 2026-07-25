"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.endpoints import ai, bookmarks, content, dashboard, health, notifications, opportunities, pipe, profiles, resume, scoring, search_providers, searches, settings, user_settings, version
from backend.core.config import get_backend_config
from backend.middleware.rate_limit import RateLimitMiddleware
from database.session import init_db
from services.background.scheduler import BackgroundScheduler
from services.background.tasks import create_and_start_scheduler
from services.memory import MemoryService

cfg = get_backend_config()

_scheduler: BackgroundScheduler | None = None
_memory: MemoryService | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator:
    global _scheduler, _memory
    init_db()
    _scheduler = create_and_start_scheduler(cfg)

    if cfg.memory.enabled:
        _memory = MemoryService(cfg)
        _memory.initialize()

    yield

    if _memory:
        _memory.close()
    if _scheduler:
        _scheduler.stop()


app = FastAPI(
    title=cfg.app_name,
    version=cfg.version,
    debug=cfg.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.server.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Only enable rate limiting in non-debug (production) mode
if not cfg.debug:
    app.add_middleware(
        RateLimitMiddleware,
        default_limit=60,
        window_seconds=60,
        route_limits={
            "/api/v1/ai/generate": 10,
            "/api/v1/pipeline/run": 5,
            "/api/v1/content/extract": 20,
        },
    )

app.include_router(health, prefix="/api/v1", tags=["health"])
app.include_router(version, prefix="/api/v1", tags=["version"])
app.include_router(settings, prefix="/api/v1", tags=["settings"])
app.include_router(profiles, prefix="/api/v1", tags=["profiles"])
app.include_router(resume, prefix="/api/v1", tags=["resume"])
app.include_router(dashboard, prefix="/api/v1", tags=["dashboard"])
app.include_router(ai, prefix="/api/v1", tags=["ai"])
app.include_router(pipe, prefix="/api/v1", tags=["pipeline"])
app.include_router(scoring, prefix="/api/v1", tags=["scoring"])
app.include_router(content, prefix="/api/v1", tags=["content"])
app.include_router(notifications, prefix="/api/v1", tags=["notifications"])
app.include_router(opportunities, prefix="/api/v1", tags=["opportunities"])
app.include_router(bookmarks, prefix="/api/v1", tags=["bookmarks"])
app.include_router(search_providers, prefix="/api/v1", tags=["search_providers"])
app.include_router(searches, prefix="/api/v1", tags=["searches"])
app.include_router(user_settings, prefix="/api/v1", tags=["user_settings"])

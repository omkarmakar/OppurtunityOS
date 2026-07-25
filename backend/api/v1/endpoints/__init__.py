"""API v1 endpoints package."""

from backend.api.v1.endpoints.ai import router as ai
from backend.api.v1.endpoints.content import router as content
from backend.api.v1.endpoints.dashboard import router as dashboard
from backend.api.v1.endpoints.health import router as health
from backend.api.v1.endpoints.notifications import router as notifications
from backend.api.v1.endpoints.pipe import router as pipe
from backend.api.v1.endpoints.profiles import router as profiles
from backend.api.v1.endpoints.resume import router as resume
from backend.api.v1.endpoints.scoring import router as scoring
from backend.api.v1.endpoints.settings import router as settings
from backend.api.v1.endpoints.version import router as version

__all__ = [
    "ai",
    "content",
    "dashboard",
    "health",
    "notifications",
    "pipe",
    "profiles",
    "resume",
    "scoring",
    "version",
    "settings",
]

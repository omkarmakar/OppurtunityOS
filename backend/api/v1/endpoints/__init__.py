"""API v1 endpoints package."""

from backend.api.v1.endpoints.ai import router as ai
from backend.api.v1.endpoints.bookmarks import router as bookmarks
from backend.api.v1.endpoints.content import router as content
from backend.api.v1.endpoints.dashboard import router as dashboard
from backend.api.v1.endpoints.health import router as health
from backend.api.v1.endpoints.notifications import router as notifications
from backend.api.v1.endpoints.opportunities import router as opportunities
from backend.api.v1.endpoints.pipe import router as pipe
from backend.api.v1.endpoints.profiles import router as profiles
from backend.api.v1.endpoints.resume import router as resume
from backend.api.v1.endpoints.scoring import router as scoring
from backend.api.v1.endpoints.search_providers import router as search_providers
from backend.api.v1.endpoints.searches import router as searches
from backend.api.v1.endpoints.settings import router as settings
from backend.api.v1.endpoints.user_settings import router as user_settings
from backend.api.v1.endpoints.users import router as users
from backend.api.v1.endpoints.version import router as version

__all__ = [
    "ai",
    "bookmarks",
    "content",
    "dashboard",
    "health",
    "notifications",
    "opportunities",
    "pipe",
    "profiles",
    "resume",
    "scoring",
    "search_providers",
    "searches",
    "user_settings",
    "users",
    "version",
    "settings",
]

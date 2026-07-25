"""Database package — models, session, and repositories."""

from database.base import Base
from database.models import (
    ApplicationSettings,
    Bookmark,
    Notification,
    Opportunity,
    Profile,
    Search,
    Source,
    User,
)
from database.repositories import (
    ApplicationSettingsRepository,
    BaseRepository,
    BookmarkRepository,
    NotificationRepository,
    OpportunityRepository,
    ProfileRepository,
    SearchRepository,
    SourceRepository,
    UserRepository,
)
from database.session import SessionLocal, engine, init_db

__all__ = [
    # base
    "Base",
    "engine",
    "SessionLocal",
    "init_db",
    # models
    "ApplicationSettings",
    "Bookmark",
    "Notification",
    "Opportunity",
    "Profile",
    "Search",
    "Source",
    "User",
    # repositories
    "ApplicationSettingsRepository",
    "BaseRepository",
    "BookmarkRepository",
    "NotificationRepository",
    "OpportunityRepository",
    "ProfileRepository",
    "SearchRepository",
    "SourceRepository",
    "UserRepository",
]

"""Repository layer — data access abstractions.

Repositories encapsulate database operations for each aggregate root.
They depend on a SQLAlchemy ``Session`` and expose the standard set of
data-access methods (get, list, add, update, delete, count, exists).
"""

from database.repositories.application_settings_repository import (
    ApplicationSettingsRepository,
)
from database.repositories.base import BaseRepository
from database.repositories.bookmark_repository import BookmarkRepository
from database.repositories.notification_repository import NotificationRepository
from database.repositories.opportunity_repository import OpportunityRepository
from database.repositories.pipeline_run_repository import PipelineRunRepository
from database.repositories.profile_repository import ProfileRepository
from database.repositories.quota_state_repository import QuotaStateRepository
from database.repositories.scheduler_state_repository import SchedulerStateRepository
from database.repositories.search_repository import SearchRepository
from database.repositories.source_repository import SourceRepository
from database.repositories.user_repository import UserRepository

__all__ = [
    "ApplicationSettingsRepository",
    "BaseRepository",
    "BookmarkRepository",
    "NotificationRepository",
    "OpportunityRepository",
    "PipelineRunRepository",
    "ProfileRepository",
    "QuotaStateRepository",
    "SchedulerStateRepository",
    "SearchRepository",
    "SourceRepository",
    "UserRepository",
]

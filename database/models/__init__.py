"""SQLAlchemy ORM model definitions.

Importing this module registers all models with ``Base.metadata``,
which is required by Alembic and ``metadata.create_all()``.
"""

from database.models.application_settings import ApplicationSettings
from database.models.bookmarks import Bookmark
from database.models.notifications import Notification
from database.models.opportunities import Opportunity
from database.models.pipeline_runs import PipelineRun
from database.models.profiles import Profile
from database.models.scheduler_state import SchedulerState
from database.models.searches import Search
from database.models.sources import Source
from database.models.users import User

__all__ = [
    "ApplicationSettings",
    "Bookmark",
    "Notification",
    "Opportunity",
    "PipelineRun",
    "Profile",
    "SchedulerState",
    "Search",
    "Source",
    "User",
]

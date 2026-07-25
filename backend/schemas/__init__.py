"""Pydantic schemas package."""

from backend.schemas.health import HealthResponse
from backend.schemas.notifications import (
    DigestTriggerResponse,
    NotificationListResponse,
    NotificationResponse,
    NotificationSettingsResponse,
    TestNotificationResponse,
    UnreadCountResponse,
    UpdateNotificationSettingsRequest,
)
from backend.schemas.profiles import (
    EducationEntry,
    ExperienceEntry,
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate,
    ProjectEntry,
    ResumeParseResponse,
)
from backend.schemas.settings import SettingsResponse
from backend.schemas.version import VersionResponse

__all__ = [
    "DigestTriggerResponse",
    "EducationEntry",
    "ExperienceEntry",
    "HealthResponse",
    "NotificationListResponse",
    "NotificationResponse",
    "NotificationSettingsResponse",
    "ProfileCreate",
    "ProfileResponse",
    "ProfileUpdate",
    "ProjectEntry",
    "ResumeParseResponse",
    "SettingsResponse",
    "TestNotificationResponse",
    "UnreadCountResponse",
    "UpdateNotificationSettingsRequest",
    "VersionResponse",
]

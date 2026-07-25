"""Notification schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    type_: str = Field(alias="type")
    title: str
    message: str | None
    is_read: bool
    channel: str
    read_at: datetime | None
    delivered_at: datetime | None
    email_to: str | None
    digest_id: UUID | None
    metadata_json: str | None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationSettingsResponse(BaseModel):
    desktop_enabled: bool
    email_enabled: bool
    digest_enabled: bool
    polling_interval_seconds: int
    smtp_host: str
    smtp_port: int
    smtp_use_tls: bool
    from_address: str
    from_name: str
    digest_schedule_hour: int
    digest_schedule_minute: int
    digest_max_opportunities: int
    digest_include_unread_only: bool


class UpdateNotificationSettingsRequest(BaseModel):
    desktop_enabled: bool | None = None
    email_enabled: bool | None = None
    digest_enabled: bool | None = None
    polling_interval_seconds: int | None = Field(default=None, ge=10, le=3600)
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool | None = None
    from_address: str | None = None
    from_name: str | None = None
    digest_schedule_hour: int | None = Field(default=None, ge=0, le=23)
    digest_schedule_minute: int | None = Field(default=None, ge=0, le=59)
    digest_max_opportunities: int | None = Field(default=None, ge=1, le=100)
    digest_include_unread_only: bool | None = None


class DigestTriggerResponse(BaseModel):
    digest_id: str
    notifications_count: int
    email_sent: bool
    message: str


class TestNotificationResponse(BaseModel):
    success: bool
    message: str

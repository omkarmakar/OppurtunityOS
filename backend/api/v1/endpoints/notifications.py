"""Notification endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_app_config, get_db
from backend.schemas.notifications import (
    DigestTriggerResponse,
    NotificationListResponse,
    NotificationResponse,
    NotificationSettingsResponse,
    TestNotificationResponse,
    UnreadCountResponse,
    UpdateNotificationSettingsRequest,
)
from core.config import AppConfig
from database.repositories.notification_repository import NotificationRepository
from services.notifications import (
    DailyDigestService,
    DesktopNotificationProvider,
    EmailNotificationProvider,
    NotificationService,
)

router = APIRouter()


def _get_notif_service(db: Session, config: AppConfig | None = None) -> NotificationService:
    return NotificationService(db, config)


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    user_id: uuid.UUID = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    channel: str | None = Query(None),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    svc = _get_notif_service(db)
    items = svc.get_notifications(user_id, limit=limit, offset=offset, unread_only=unread_only, channel=channel)
    total = svc.get_total_count(user_id)
    unread_count = svc.count_unread(user_id)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
    )


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def unread_count(
    user_id: uuid.UUID = Query(..., description="User ID"),
    db: Session = Depends(get_db),
) -> UnreadCountResponse:
    svc = _get_notif_service(db)
    return UnreadCountResponse(unread_count=svc.count_unread(user_id))


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> NotificationResponse:
    svc = _get_notif_service(db)
    notif = svc.mark_as_read(notification_id)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationResponse.model_validate(notif)


@router.post("/notifications/mark-all-read", response_model=dict[str, int])
def mark_all_as_read(
    user_id: uuid.UUID = Query(..., description="User ID"),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    svc = _get_notif_service(db)
    count = svc.mark_all_as_read(user_id)
    db.commit()
    return {"marked": count}


@router.get("/notifications/settings", response_model=NotificationSettingsResponse)
def get_notification_settings(
    config: AppConfig = Depends(get_app_config),
) -> NotificationSettingsResponse:
    ns = config.notifications
    return NotificationSettingsResponse(
        desktop_enabled=ns.desktop_enabled,
        email_enabled=ns.email_enabled,
        digest_enabled=ns.digest_enabled,
        polling_interval_seconds=ns.polling_interval_seconds,
        smtp_host=ns.email.smtp_host,
        smtp_port=ns.email.smtp_port,
        smtp_use_tls=ns.email.smtp_use_tls,
        from_address=ns.email.from_address,
        from_name=ns.email.from_name,
        digest_schedule_hour=ns.digest.schedule_hour,
        digest_schedule_minute=ns.digest.schedule_minute,
        digest_max_opportunities=ns.digest.max_opportunities,
        digest_include_unread_only=ns.digest.include_unread_only,
    )


@router.put("/notifications/settings", response_model=NotificationSettingsResponse)
def update_notification_settings(
    data: UpdateNotificationSettingsRequest,
    config: AppConfig = Depends(get_app_config),
) -> NotificationSettingsResponse:
    ns = config.notifications
    patch = data.model_dump(exclude_unset=True)
    if "desktop_enabled" in patch:
        ns.desktop_enabled = patch["desktop_enabled"]
    if "email_enabled" in patch:
        ns.email_enabled = patch["email_enabled"]
    if "digest_enabled" in patch:
        ns.digest_enabled = patch["digest_enabled"]
    if "polling_interval_seconds" in patch:
        ns.polling_interval_seconds = patch["polling_interval_seconds"]
    email_fields = {"smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_use_tls", "from_address", "from_name"}
    digest_fields = {"digest_schedule_hour", "digest_schedule_minute", "digest_max_opportunities", "digest_include_unread_only"}
    for key, value in patch.items():
        if key in email_fields:
            setattr(ns.email, key.replace("smtp_", "smtp_"), value)
        elif key in digest_fields:
            setattr(ns.digest, key.replace("digest_", ""), value)
    return get_notification_settings(config=config)


@router.post("/notifications/digest/trigger", response_model=DigestTriggerResponse)
def trigger_digest(
    user_id: uuid.UUID = Query(..., description="User ID"),
    user_email: str = Query("", description="Optional email for digest delivery"),
    db: Session = Depends(get_db),
    config: AppConfig = Depends(get_app_config),
) -> DigestTriggerResponse:
    email_provider = None
    if config.notifications.email_enabled and user_email:
        es = config.notifications.email
        email_provider = EmailNotificationProvider(
            host=es.smtp_host,
            port=es.smtp_port,
            username=es.smtp_username,
            password=es.smtp_password,
            use_tls=es.smtp_use_tls,
            from_address=es.from_address,
            from_name=es.from_name,
        )
    digest_svc = DailyDigestService(db, email_provider=email_provider, settings=config.notifications.digest)
    result = digest_svc.run(user_id, user_email=user_email)
    if result.get("digest_id"):
        db.commit()
    cnt = result.get("notifications_count", 0)
    return DigestTriggerResponse(
        digest_id=result.get("digest_id") or "",
        notifications_count=cnt,
        email_sent=result.get("email_sent", False),
        message=f"Digest created with {cnt} notification(s)" + (" and emailed" if result.get("email_sent") else ""),
    )


@router.post("/notifications/test-desktop", response_model=TestNotificationResponse)
def test_desktop_notification(
    title: str = Query("Test Notification"),
    message: str = Query("This is a test desktop notification"),
) -> TestNotificationResponse:
    try:
        provider = DesktopNotificationProvider()
        success = provider.send("test", title, message)
        return TestNotificationResponse(success=success, message="Sent" if success else "Not available (no system tray)")
    except Exception as exc:
        return TestNotificationResponse(success=False, message=str(exc))


@router.post("/notifications/test-email", response_model=TestNotificationResponse)
def test_email_notification(
    email_to: str = Query(..., description="Recipient email address"),
    title: str = Query("Test Notification from OpportunityOS"),
    message: str = Query("This is a test email notification."),
    config: AppConfig = Depends(get_app_config),
) -> TestNotificationResponse:
    try:
        es = config.notifications.email
        provider = EmailNotificationProvider(
            host=es.smtp_host,
            port=es.smtp_port,
            username=es.smtp_username,
            password=es.smtp_password,
            use_tls=es.smtp_use_tls,
            from_address=es.from_address,
            from_name=es.from_name,
        )
        success = provider.send("test", title, message, email_to=email_to)
        return TestNotificationResponse(success=success, message="Email sent" if success else "Email sending failed")
    except Exception as exc:
        return TestNotificationResponse(success=False, message=str(exc))

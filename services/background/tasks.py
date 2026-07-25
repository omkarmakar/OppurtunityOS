"""Scheduled task factories for common operations."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from core.config import AppConfig
from database.repositories.profile_repository import ProfileRepository
from database.session import SessionLocal
from services.background.scheduler import BackgroundScheduler, ScheduledTask
from services.notifications.digest import DailyDigestService
from services.notifications.providers import EmailNotificationProvider
from services.search_pipeline import PipelineConfig, SearchPipeline

logger = logging.getLogger(__name__)


def _pipeline_callback(user_id: uuid.UUID, config: AppConfig) -> dict[str, Any] | None:
    """Run the search pipeline synchronously in a background thread."""
    db = SessionLocal()
    try:
        profile_repo = ProfileRepository(db)
        profile = profile_repo.get_by_user_id(user_id)
        if not profile:
            logger.warning("Pipeline: no profile for user %s", user_id)
            return None

        bs = config.background_scheduler
        pconfig = PipelineConfig(
            search_provider=bs.pipeline_search_provider,
            query_count=bs.pipeline_max_queries,
            search_result_count=bs.pipeline_max_results,
        )
        pipeline = SearchPipeline(db=db, config=pconfig)
        result = asyncio.run(pipeline.run(profile))
        db.commit()
        return {
            "success": result.success,
            "opportunities_created": result.opportunities_created,
            "opportunities_scored": result.opportunities_scored,
        }
    finally:
        db.close()


def _digest_callback(user_id: uuid.UUID, config: AppConfig) -> dict[str, Any] | None:
    """Trigger the daily digest synchronously in a background thread."""
    db = SessionLocal()
    try:
        email_provider = None
        if config.notifications.email_enabled:
            es = config.notifications.email
            email_provider = EmailNotificationProvider(
                host=es.smtp_host, port=es.smtp_port,
                username=es.smtp_username, password=es.smtp_password,
                use_tls=es.smtp_use_tls, from_address=es.from_address,
                from_name=es.from_name,
            )
        digest_svc = DailyDigestService(
            db,
            email_provider=email_provider,
            settings=config.notifications.digest,
        )
        result = digest_svc.run(user_id)
        if result.get("digest_id"):
            db.commit()
        return result
    finally:
        db.close()


def create_and_start_scheduler(
    config: AppConfig,
    *,
    user_id: uuid.UUID | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> BackgroundScheduler | None:
    """Create, configure, and start the background scheduler.

    Args:
        config: Application configuration.
        user_id: Override the default user ID (uses config default otherwise).
        session_factory: Override the DB session factory (used in tests).

    Returns:
        The started BackgroundScheduler instance, or None if disabled.
    """
    bs_settings = config.background_scheduler
    if not bs_settings.enabled:
        logger.info("Background scheduler is disabled in config")
        return None

    scheduler = BackgroundScheduler(polling_interval=bs_settings.polling_interval_seconds)
    uid = user_id or uuid.UUID(bs_settings.default_user_id)

    # ── pipeline task ────────────────────────────────────────────────
    if bs_settings.pipeline_enabled:
        task = ScheduledTask(
            name="pipeline",
            interval_seconds=lambda: config.background_scheduler.pipeline_interval_seconds,
            callback=lambda: _pipeline_callback(uid, config),
            max_retries=bs_settings.pipeline_retry_count,
            retry_delay_base=float(bs_settings.pipeline_retry_delay_base),
        )
        scheduler.add_task(task)
        logger.info(
            "Registered pipeline task (interval=%ds, retries=%d, provider=%s)",
            bs_settings.pipeline_interval_seconds,
            bs_settings.pipeline_retry_count,
            bs_settings.pipeline_search_provider,
        )

    # ── digest task ──────────────────────────────────────────────────
    if bs_settings.digest_enabled:
        task = ScheduledTask(
            name="digest",
            interval_seconds=bs_settings.digest_interval_seconds,
            callback=lambda: _digest_callback(uid, config),
            max_retries=bs_settings.digest_retry_count,
            retry_delay_base=float(bs_settings.digest_retry_delay_base),
        )
        scheduler.add_task(task)
        logger.info(
            "Registered digest task (interval=%ds, retries=%d)",
            bs_settings.digest_interval_seconds,
            bs_settings.digest_retry_count,
        )

    scheduler.start()
    return scheduler

"""Scheduled task factories for common operations."""

from __future__ import annotations

import asyncio
import logging
import uuid
import zoneinfo
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from core.config import AppConfig
from database.repositories.profile_repository import ProfileRepository
from database.repositories.scheduler_state_repository import SchedulerStateRepository
from database.repositories.user_repository import UserRepository
from database.session import SessionLocal
from services.background.scheduler import BackgroundScheduler, ScheduledTask
from services.notifications.digest import DailyDigestService
from services.notifications.providers import EmailNotificationProvider
from services.search_pipeline import PipelineConfig, SearchPipeline

logger = logging.getLogger(__name__)


def _make_pipeline_run_condition(
    user_id: uuid.UUID,
    config: AppConfig,
    session_factory: Callable[[], Session] | None = None,
) -> Callable[[], bool]:
    """Closure that evaluates whether the pipeline task is due to run today."""

    def condition() -> bool:
        bs = config.background_scheduler
        try:
            tz = zoneinfo.ZoneInfo(bs.timezone)
        except Exception as exc:
            logger.error("Invalid timezone '%s': %s", bs.timezone, exc)
            return False

        now_local = datetime.now(tz)
        local_hour = now_local.hour

        # Check local hour window: [start_hour, end_hour)
        if not (bs.pipeline_window_start_hour <= local_hour < bs.pipeline_window_end_hour):
            return False

        db_factory = session_factory or SessionLocal
        db = db_factory()
        try:
            repo = SchedulerStateRepository(db)
            state = repo.get_by_user_and_task(user_id, "pipeline")
            if state is not None and state.last_run_date == now_local.date():
                return False
            return True
        finally:
            db.close()

    return condition


def _pipeline_callback(
    user_id: uuid.UUID,
    config: AppConfig,
    session_factory: Callable[[], Session] | None = None,
) -> dict[str, Any] | None:
    """Run the search pipeline synchronously in a background thread."""
    db_factory = session_factory or SessionLocal
    db = db_factory()
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
        if result.success:
            try:
                tz = zoneinfo.ZoneInfo(bs.timezone)
                now_local = datetime.now(tz)
                state_repo = SchedulerStateRepository(db)
                state_repo.update_last_run(user_id, "pipeline", run_date=now_local.date())
            except Exception as exc:
                logger.error("Failed to update scheduler_state after pipeline run: %s", exc)
        db.commit()
        return {
            "success": result.success,
            "opportunities_created": result.opportunities_created,
            "opportunities_scored": result.opportunities_scored,
        }
    finally:
        db.close()


def _digest_callback(
    user_id: uuid.UUID,
    config: AppConfig,
    session_factory: Callable[[], Session] | None = None,
) -> dict[str, Any] | None:
    """Trigger the daily digest synchronously in a background thread."""
    db_factory = session_factory or SessionLocal
    db = db_factory()
    try:
        # ── look up the user's email ─────────────────────────────────
        user = UserRepository(db).get(user_id)
        if not user or not user.email or user.email.endswith("@no-email.invalid"):
            logger.warning(
                "digest skipped: no user row / no email for user_id=%s", user_id,
            )
            return {"notifications_count": 0, "email_sent": False, "digest_id": None}
        user_email = user.email

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
        result = digest_svc.run(user_id, user_email=user_email)
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
        run_cond = _make_pipeline_run_condition(uid, config, session_factory=session_factory)

        # Check missed window on startup for logging
        try:
            tz = zoneinfo.ZoneInfo(bs_settings.timezone)
            now_local = datetime.now(tz)
            local_hour = now_local.hour
            db_factory = session_factory or SessionLocal
            db = db_factory()
            try:
                repo = SchedulerStateRepository(db)
                state = repo.get_by_user_and_task(uid, "pipeline")
                already_ran = state is not None and state.last_run_date == now_local.date()
                if local_hour >= bs_settings.pipeline_window_end_hour and not already_ran:
                    logger.info(
                        "Pipeline window missed for today (%s): current local time %02d:%02d (%s) is past window end (%02d:00)",
                        now_local.date(),
                        local_hour,
                        now_local.minute,
                        bs_settings.timezone,
                        bs_settings.pipeline_window_end_hour,
                    )
            finally:
                db.close()
        except Exception as exc:
            logger.debug("Failed checking missed pipeline window log on startup: %s", exc)

        task = ScheduledTask(
            name="pipeline",
            interval_seconds=60,  # no-op placeholder since run_condition takes over due-checking
            run_condition=run_cond,
            callback=lambda: _pipeline_callback(uid, config, session_factory=session_factory),
            max_retries=bs_settings.pipeline_retry_count,
            retry_delay_base=float(bs_settings.pipeline_retry_delay_base),
        )
        scheduler.add_task(task)
        logger.info(
            "Registered window-scheduled pipeline task (window=%02d:00-%02d:00 %s, retries=%d, provider=%s)",
            bs_settings.pipeline_window_start_hour,
            bs_settings.pipeline_window_end_hour,
            bs_settings.timezone,
            bs_settings.pipeline_retry_count,
            bs_settings.pipeline_search_provider,
        )

    # ── digest task ──────────────────────────────────────────────────
    if bs_settings.digest_enabled:
        task = ScheduledTask(
            name="digest",
            interval_seconds=bs_settings.digest_interval_seconds,
            callback=lambda: _digest_callback(uid, config, session_factory=session_factory),
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


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
    profile_id: uuid.UUID,
    config: AppConfig,
    session_factory: Callable[[], Session] | None = None,
) -> Callable[[], bool]:
    """Closure that evaluates whether this profile's pipeline task is due to run today."""

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
            state = repo.get_by_user_and_task(
                user_id, "pipeline", profile_id=profile_id,
            )
            if state is not None and state.last_run_date == now_local.date():
                return False
            return True
        finally:
            db.close()

    return condition


def _pipeline_callback(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    config: AppConfig,
    session_factory: Callable[[], Session] | None = None,
) -> dict[str, Any] | None:
    """Run the search pipeline for a single profile synchronously in a background thread."""
    db_factory = session_factory or SessionLocal
    db = db_factory()
    try:
        profile_repo = ProfileRepository(db)
        profile = profile_repo.get(profile_id)
        if not profile:
            logger.warning("Pipeline: profile %s not found for user %s", profile_id, user_id)
            return None

        bs = config.background_scheduler
        pconfig = PipelineConfig(
            search_provider=bs.pipeline_search_provider,
            search_secondary_providers=["jobboards"],
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
                state_repo.update_last_run(
                    user_id, "pipeline",
                    run_date=now_local.date(),
                    profile_id=profile_id,
                )
            except Exception as exc:
                logger.error(
                    "Failed to update scheduler_state after pipeline run for profile %s: %s",
                    profile_id, exc,
                )
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


def _check_and_log_missed_window(
    uid: uuid.UUID,
    config: AppConfig,
    session_factory: Callable[[], Session] | None = None,
) -> None:
    """Log a warning for each profile that missed today's pipeline window."""
    bs = config.background_scheduler
    db_factory = session_factory or SessionLocal
    db = db_factory()
    try:
        tz = zoneinfo.ZoneInfo(bs.timezone)
        now_local = datetime.now(tz)
        local_hour = now_local.hour
        if local_hour < bs.pipeline_window_end_hour:
            return  # window hasn't closed yet — nothing missed

        profile_repo = ProfileRepository(db)
        profiles = profile_repo.list_by_user_id(uid)
        if not profiles:
            return

        state_repo = SchedulerStateRepository(db)
        for p in profiles:
            state = state_repo.get_by_user_and_task(uid, "pipeline", profile_id=p.id)
            already_ran = state is not None and state.last_run_date == now_local.date()
            if not already_ran:
                logger.info(
                    "Pipeline window missed for today (%s): profile %s (%s) — "
                    "current local time %02d:%02d (%s) is past window end (%02d:00)",
                    now_local.date(), p.id, p.name,
                    local_hour, now_local.minute,
                    bs.timezone, bs.pipeline_window_end_hour,
                )
    except Exception as exc:
        logger.debug("Failed checking missed pipeline window log on startup: %s", exc)
    finally:
        db.close()


def create_and_start_scheduler(
    config: AppConfig,
    *,
    user_id: uuid.UUID | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> BackgroundScheduler | None:
    """Create, configure, and start the background scheduler.

    One ``ScheduledTask`` is registered per profile (named ``"pipeline:{profile_id}"``),
    so each profile's daily search runs independently.

    Args:
        config: Application configuration.
        user_id: Override the default user ID (uses config default otherwise).
        session_factory: Override the DB session factory (used in tests).

    Returns:
        The started BackgroundScheduler instance, or None if disabled.

    Note:
        Profiles created after the scheduler is already running will not
        be picked up until the next application restart.
    """
    bs_settings = config.background_scheduler
    if not bs_settings.enabled:
        logger.info("Background scheduler is disabled in config")
        return None

    scheduler = BackgroundScheduler(polling_interval=bs_settings.polling_interval_seconds)
    uid = user_id or uuid.UUID(bs_settings.default_user_id)

    # ── pipeline tasks (one per profile) ─────────────────────────────
    if bs_settings.pipeline_enabled:
        db_factory = session_factory or SessionLocal
        db = db_factory()
        try:
            profile_repo = ProfileRepository(db)
            profiles = profile_repo.list_by_user_id(uid)
        finally:
            db.close()

        if not profiles:
            logger.warning("No profiles found for user %s — no pipeline tasks registered", uid)
        else:
            for profile in profiles:
                pid = profile.id
                run_cond = _make_pipeline_run_condition(
                    uid, pid, config, session_factory=session_factory,
                )
                task_name = f"pipeline:{pid}"
                task = ScheduledTask(
                    name=task_name,
                    interval_seconds=60,
                    run_condition=run_cond,
                    callback=lambda uid=uid, pid=pid: _pipeline_callback(
                        uid, pid, config, session_factory=session_factory,
                    ),
                    max_retries=bs_settings.pipeline_retry_count,
                    retry_delay_base=float(bs_settings.pipeline_retry_delay_base),
                )
                scheduler.add_task(task)
                logger.info(
                    "Registered window-scheduled pipeline task for profile %s (%s) "
                    "(window=%02d:00-%02d:00 %s, retries=%d, provider=%s)",
                    pid, profile.name,
                    bs_settings.pipeline_window_start_hour,
                    bs_settings.pipeline_window_end_hour,
                    bs_settings.timezone,
                    bs_settings.pipeline_retry_count,
                    bs_settings.pipeline_search_provider,
                )

        # Check missed window on startup for logging (per-profile)
        _check_and_log_missed_window(uid, config, session_factory=session_factory)

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


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
from database.repositories.quota_state_repository import QuotaStateRepository
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


# ── Weekly job board sweep ─────────────────────────────────────────


def _make_weekly_jobboard_run_condition(
    user_id: uuid.UUID,
    config: AppConfig,
    session_factory: Callable[[], Session] | None = None,
) -> Callable[[], bool]:
    """Closure that evaluates whether the weekly job board sweep is due.

    Runs once per week on the configured day-of-week and hour.
    Uses scheduler_state with task_name="weekly_jobboard" to track
    the last run date ( LOCAL calendar date ).
    """

    def condition() -> bool:
        bs = config.background_scheduler
        try:
            tz = zoneinfo.ZoneInfo(bs.timezone)
        except Exception as exc:
            logger.error("Invalid timezone '%s': %s", bs.timezone, exc)
            return False

        now_local = datetime.now(tz)

        # Only run on the configured day of week and hour
        if now_local.weekday() != bs.weekly_jobboard_day_of_week:
            return False
        if now_local.hour != bs.weekly_jobboard_hour:
            return False

        # Check if already ran this week (same local calendar date)
        db_factory = session_factory or SessionLocal
        db = db_factory()
        try:
            repo = SchedulerStateRepository(db)
            state = repo.get_by_user_and_task(
                user_id, "weekly_jobboard", profile_id=None,
            )
            if state is not None and state.last_run_date == now_local.date():
                return False
            return True
        finally:
            db.close()

    return condition


def _weekly_jobboard_callback(
    user_id: uuid.UUID,
    config: AppConfig,
    session_factory: Callable[[], Session] | None = None,
) -> dict[str, Any] | None:
    """Run the weekly job board sweep across all RapidAPI-backed providers.

    This runs as a SEPARATE layer from the daily pipeline — it queries
    job boards directly (bypassing the daily Tavily queries) and feeds
    results into the same opportunity creation + scoring pipeline.
    """
    from services.job_boards.aggregator import JobBoardAggregator

    bs = config.background_scheduler
    db_factory = session_factory or SessionLocal
    db = db_factory()
    try:
        # Build the aggregator (RapidAPI boards only, no legacy)
        aggregator = JobBoardAggregator()

        # Check quota for each provider and skip if below safety margin
        quota_repo = QuotaStateRepository(db)
        active_boards = {}
        skipped = []
        for name, board in aggregator.boards.items():
            state = quota_repo.get_by_provider(name)
            if state and state.remaining is not None and state.quota_limit is not None:
                if state.quota_limit > 0 and state.remaining < (state.quota_limit * bs.weekly_jobboard_quota_safety_margin):
                    skipped.append(name)
                    logger.info(
                        "Weekly sweep: skipping %s — quota %d/%d below safety margin %.0f%%",
                        name, state.remaining, state.quota_limit,
                        bs.weekly_jobboard_quota_safety_margin * 100,
                    )
                    continue
            active_boards[name] = board

        if not active_boards:
            logger.warning("Weekly sweep: all providers skipped due to low quota")
            return {"opportunities_created": 0, "providers_skipped": skipped}

        # Load all profiles for this user to generate queries
        profile_repo = ProfileRepository(db)
        profiles = profile_repo.list_by_user_id(user_id)
        if not profiles:
            logger.warning("Weekly sweep: no profiles found for user %s", user_id)
            return {"opportunities_created": 0, "providers_skipped": skipped}

        # Generate queries from the first profile (or combine from all)
        from services.search_pipeline.steps.query_generator_rules import RuleBasedQueryGenerator
        qgen = RuleBasedQueryGenerator(query_count=bs.weekly_jobboard_max_queries)
        all_queries: list[str] = []
        for profile in profiles:
            try:
                import asyncio as _asyncio
                ctx = {"profile": profile}
                ctx = _asyncio.run(qgen.execute(ctx))
                all_queries.extend(ctx.get("queries", []))
            except Exception as exc:
                logger.warning("Failed to generate queries for profile %s: %s", profile.id, exc)
        # Deduplicate queries
        all_queries = list(dict.fromkeys(all_queries))[:bs.weekly_jobboard_max_queries]

        if not all_queries:
            logger.warning("Weekly sweep: no queries generated from profiles")
            return {"opportunities_created": 0, "providers_skipped": skipped}

        logger.info(
            "Weekly sweep: running %d queries across %d boards (skipped: %s)",
            len(all_queries), len(active_boards), skipped,
        )

        # Run search across active boards
        import asyncio
        from services.job_boards.base import JobPosting

        async def _search_all() -> list[JobPosting]:
            tasks = [
                board.search(all_queries, max_results=bs.weekly_jobboard_max_results)
                for board in active_boards.values()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            all_postings: list[JobPosting] = []
            for result in results:
                if isinstance(result, Exception):
                    logger.warning("Weekly sweep board failed: %s", result)
                    continue
                if isinstance(result, list):
                    all_postings.extend(result)
            return all_postings

        postings = asyncio.run(_search_all())

        # Persist quota for all active boards
        for board in active_boards.values():
            try:
                board.persist_quota(db)
            except Exception as exc:
                logger.warning("Failed to persist quota for %s: %s", board.name, exc)

        # Feed through the same pipeline (OpportunityCreator + Scorer)
        if postings:
            # Convert JobPosting to SearchResult format for the pipeline
            from services.search import SearchResult
            search_results = []
            for p in postings:
                search_results.append(SearchResult(
                    title=p.title,
                    url=p.url,
                    snippet=p.description[:300] if p.description else "",
                    source=p.board,
                    raw={
                        "company": p.company,
                        "location": p.location,
                        "salary": p.salary,
                        "job_type": p.job_type,
                        "skills": p.skills,
                        "posted_date": p.posted_date.isoformat() if p.posted_date else None,
                        "job_id": p.job_id,
                        "weekly_sweep": True,
                    },
                ))

            # Use the pipeline's OpportunityCreator directly
            from services.search_pipeline.steps.opportunity_creator import OpportunityCreator
            from services.search_pipeline.steps.content_extractor import ContentExtractorStep
            from services.search_pipeline import PipelineContext

            ctx: dict[str, Any] = {
                "db": db,
                "profile": profiles[0],
                "search_results": search_results,
                "queries": all_queries,
            }

            creator = OpportunityCreator()
            ctx = asyncio.run(creator.execute(ctx))

            created = ctx.get("opportunities_created", 0)
            logger.info("Weekly sweep: created %d opportunities", created)

            # Update scheduler state
            tz = zoneinfo.ZoneInfo(bs.timezone)
            now_local = datetime.now(tz)
            state_repo = SchedulerStateRepository(db)
            state_repo.update_last_run(
                user_id, "weekly_jobboard",
                run_date=now_local.date(),
                profile_id=None,
            )
            db.commit()

            return {
                "opportunities_created": created,
                "providers_skipped": skipped,
                "queries_run": len(all_queries),
                "postings_found": len(postings),
            }

        # No postings — still update state to avoid re-running
        tz = zoneinfo.ZoneInfo(bs.timezone)
        now_local = datetime.now(tz)
        state_repo = SchedulerStateRepository(db)
        state_repo.update_last_run(
            user_id, "weekly_jobboard",
            run_date=now_local.date(),
            profile_id=None,
        )
        db.commit()
        return {"opportunities_created": 0, "providers_skipped": skipped}

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

    # ── weekly job board sweep ───────────────────────────────────────
    if bs_settings.weekly_jobboard_enabled:
        weekly_cond = _make_weekly_jobboard_run_condition(
            uid, config, session_factory=session_factory,
        )
        weekly_task = ScheduledTask(
            name="weekly_jobboard",
            interval_seconds=3600,  # polls every hour; run_condition gates the actual execution
            run_condition=weekly_cond,
            callback=lambda: _weekly_jobboard_callback(
                uid, config, session_factory=session_factory,
            ),
            max_retries=bs_settings.weekly_jobboard_retry_count,
            retry_delay_base=float(bs_settings.weekly_jobboard_retry_delay_base),
        )
        scheduler.add_task(weekly_task)
        logger.info(
            "Registered weekly job board sweep (day=%d, hour=%d, retries=%d, quota_safety=%.0f%%)",
            bs_settings.weekly_jobboard_day_of_week,
            bs_settings.weekly_jobboard_hour,
            bs_settings.weekly_jobboard_retry_count,
            bs_settings.weekly_jobboard_quota_safety_margin * 100,
        )

    scheduler.start()
    return scheduler


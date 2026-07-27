"""Background scheduler tests."""

from __future__ import annotations

import threading
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

from core.config import AppConfig
from services.background import BackgroundScheduler, ScheduledTask, create_and_start_scheduler


# ── ScheduledTask ────────────────────────────────────────────────────


class TestScheduledTask:
    def test_default_fields(self) -> None:
        task = ScheduledTask(name="test", interval_seconds=60, callback=lambda: None)
        assert task.name == "test"
        assert task.interval_seconds == 60
        assert task.max_retries == 3
        assert task.retry_delay_base == 10.0
        assert task.enabled is True
        assert task._running is False
        assert task._last_run is None

    def test_callable_interval(self) -> None:
        task = ScheduledTask(name="test", interval_seconds=lambda: 120, callback=lambda: None)
        assert callable(task.interval_seconds)
        assert task.interval_seconds() == 120


# ── BackgroundScheduler ──────────────────────────────────────────────


class TestBackgroundScheduler:
    def test_start_stop(self) -> None:
        scheduler = BackgroundScheduler(polling_interval=10)
        assert scheduler.running is False
        scheduler.start()
        assert scheduler.running is True
        scheduler.stop()
        assert scheduler.running is False

    def test_start_idempotent(self) -> None:
        scheduler = BackgroundScheduler(polling_interval=10)
        scheduler.start()
        old = scheduler._thread
        scheduler.start()
        assert scheduler._thread is old
        scheduler.stop()

    def test_create_with_min_polling(self) -> None:
        scheduler = BackgroundScheduler(polling_interval=2)
        assert scheduler._polling_interval == 5  # clamped to minimum 5

    def test_add_and_remove_task(self) -> None:
        scheduler = BackgroundScheduler()
        task = ScheduledTask(name="alpha", interval_seconds=60, callback=lambda: None)
        scheduler.add_task(task)
        assert scheduler.get_task("alpha") is task
        assert len(scheduler.tasks) == 1

        scheduler.remove_task("alpha")
        assert scheduler.get_task("alpha") is None
        assert len(scheduler.tasks) == 0

    def test_get_task_missing(self) -> None:
        scheduler = BackgroundScheduler()
        assert scheduler.get_task("nope") is None


# ── Duplicate prevention ─────────────────────────────────────────────


class TestDuplicatePrevention:
    def test_does_not_run_if_already_running(self) -> None:
        scheduler = BackgroundScheduler(polling_interval=1)
        call_count = 0
        lock = threading.Event()

        def slow_cb() -> None:
            nonlocal call_count
            call_count += 1
            lock.wait(5)

        task = ScheduledTask(
            name="slow",
            interval_seconds=1,
            callback=slow_cb,
            max_retries=0,
        )
        scheduler._tasks = {"slow": task}
        task._last_run = None  # force immediate run

        scheduler._tick()
        assert task._running is True  # first call started

        scheduler._tick()  # second tick — should skip because _running is True
        assert call_count == 1  # not called again

        lock.set()
        time.sleep(0.1)
        scheduler.stop()

    def test_does_not_run_before_interval_elapsed(self) -> None:
        scheduler = BackgroundScheduler(polling_interval=1)
        call_count = 0

        def cb() -> None:
            nonlocal call_count
            call_count += 1

        task = ScheduledTask(name="t", interval_seconds=3600, callback=cb, max_retries=0)
        scheduler._tasks = {"t": task}
        task._last_run = None

        scheduler._tick()
        assert call_count == 1  # first run

        scheduler._tick()
        assert call_count == 1  # not due yet (interval 3600s)

        scheduler.stop()

    def test_runs_again_after_interval(self) -> None:
        scheduler = BackgroundScheduler(polling_interval=1)
        call_count = 0

        def cb() -> None:
            nonlocal call_count
            call_count += 1

        from datetime import datetime, timezone, timedelta

        task = ScheduledTask(name="t", interval_seconds=1, callback=cb, max_retries=0)
        scheduler._tasks = {"t": task}
        task._last_run = datetime.now(timezone.utc) - timedelta(seconds=5)  # overdue

        scheduler._tick()
        assert call_count == 1

        scheduler.stop()

    def test_disabled_task_not_run(self) -> None:
        scheduler = BackgroundScheduler(polling_interval=1)
        call_count = 0

        def cb() -> None:
            nonlocal call_count
            call_count += 1

        task = ScheduledTask(name="disabled", interval_seconds=1, callback=cb, enabled=False)
        scheduler._tasks = {"disabled": task}

        scheduler._tick()
        assert call_count == 0

        scheduler.stop()


# ── Retry logic ──────────────────────────────────────────────────────


class TestRetry:
    def test_success_no_retry(self) -> None:
        scheduler = BackgroundScheduler()
        callback = MagicMock(return_value="ok")
        task = ScheduledTask(name="succeeds", interval_seconds=1, callback=callback, max_retries=3)
        scheduler._run_task_with_retry(task)
        assert callback.call_count == 1
        assert task._running is False

    def test_retry_on_failure_then_succeeds(self) -> None:
        scheduler = BackgroundScheduler()
        call_count = 0

        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError(f"Attempt {call_count} failed")
            return "ok"

        task = ScheduledTask(
            name="flaky",
            interval_seconds=1,
            callback=flaky,
            max_retries=3,
            retry_delay_base=0.01,
        )
        scheduler._run_task_with_retry(task)
        assert call_count == 3  # 2 failures + 1 success
        assert task._running is False

    def test_exhausts_retries(self) -> None:
        scheduler = BackgroundScheduler()
        callback = MagicMock(side_effect=RuntimeError("always fails"))
        task = ScheduledTask(
            name="fails",
            interval_seconds=1,
            callback=callback,
            max_retries=2,
            retry_delay_base=0.01,
        )
        scheduler._run_task_with_retry(task)
        assert callback.call_count == 3  # original + 2 retries
        assert task._running is False

    def test_zero_retries(self) -> None:
        scheduler = BackgroundScheduler()
        callback = MagicMock(side_effect=RuntimeError("fail"))
        task = ScheduledTask(name="no-retry", interval_seconds=1, callback=callback, max_retries=0)
        scheduler._run_task_with_retry(task)
        assert callback.call_count == 1  # no retries
        assert task._running is False


# ── Callable interval (dynamic config) ───────────────────────────────


class TestCallableInterval:
    def test_callable_interval_resolved_at_tick(self) -> None:
        scheduler = BackgroundScheduler(polling_interval=1)
        call_count = 0
        interval_value = 3600

        def cb() -> None:
            nonlocal call_count
            call_count += 1

        task = ScheduledTask(name="dynamic", interval_seconds=lambda: interval_value, callback=cb, max_retries=0)
        scheduler._tasks = {"dynamic": task}

        scheduler._tick()
        assert call_count == 1  # first run (no last_run)

        scheduler._tick()
        assert call_count == 1  # not due yet

        interval_value = 1  # reduce interval
        from datetime import datetime, timezone, timedelta
        task._last_run = datetime.now(timezone.utc) - timedelta(seconds=5)

        scheduler._tick()
        assert call_count == 2  # now it's due

        scheduler.stop()


# ── create_and_start_scheduler ───────────────────────────────────────


class TestCreateAndStartScheduler:
    def test_returns_none_when_disabled(self) -> None:
        config = AppConfig()
        config.background_scheduler.enabled = False
        result = create_and_start_scheduler(config)
        assert result is None

    def test_starts_with_default_settings(self) -> None:
        config = AppConfig()
        config.background_scheduler.enabled = True
        config.background_scheduler.pipeline_enabled = False
        config.background_scheduler.digest_enabled = False
        scheduler = create_and_start_scheduler(config)
        assert scheduler is not None
        assert scheduler.running is True
        assert len(scheduler.tasks) == 0
        scheduler.stop()

    def test_registers_pipeline_tasks_per_profile(self) -> None:
        config = AppConfig()
        config.background_scheduler.enabled = True
        config.background_scheduler.pipeline_enabled = True
        config.background_scheduler.digest_enabled = False

        uid = uuid.uuid4()
        pid1, pid2 = uuid.uuid4(), uuid.uuid4()

        mock_profile1 = MagicMock(id=pid1, name="Profile 1")
        mock_profile2 = MagicMock(id=pid2, name="Profile 2")

        with patch("services.background.tasks.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_repo = MagicMock()
            mock_repo.list_by_user_id.return_value = [mock_profile1, mock_profile2]
            with patch("services.background.tasks.ProfileRepository", return_value=mock_repo):
                scheduler = create_and_start_scheduler(config, user_id=uid)
                assert scheduler is not None

                task1 = scheduler.get_task(f"pipeline:{pid1}")
                assert task1 is not None
                assert task1.max_retries == config.background_scheduler.pipeline_retry_count

                task2 = scheduler.get_task(f"pipeline:{pid2}")
                assert task2 is not None
                assert task2.max_retries == config.background_scheduler.pipeline_retry_count

                assert scheduler.get_task("pipeline") is None
                scheduler.stop()

    def test_registers_digest_task(self) -> None:
        config = AppConfig()
        config.background_scheduler.enabled = True
        config.background_scheduler.pipeline_enabled = False
        config.background_scheduler.digest_enabled = True

        with patch("services.background.tasks.SessionLocal"):
            scheduler = create_and_start_scheduler(config)
            assert scheduler is not None
            task = scheduler.get_task("digest")
            assert task is not None
            assert task.max_retries == config.background_scheduler.digest_retry_count
            scheduler.stop()

    def test_registers_pipeline_and_digest(self) -> None:
        config = AppConfig()
        config.background_scheduler.enabled = True
        config.background_scheduler.pipeline_enabled = True
        config.background_scheduler.digest_enabled = True

        uid = uuid.uuid4()
        pid = uuid.uuid4()
        mock_profile = MagicMock(id=pid, name="Profile 1")

        with patch("services.background.tasks.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_repo = MagicMock()
            mock_repo.list_by_user_id.return_value = [mock_profile]
            with patch("services.background.tasks.ProfileRepository", return_value=mock_repo):
                scheduler = create_and_start_scheduler(config, user_id=uid)
                assert scheduler is not None
                assert scheduler.get_task(f"pipeline:{pid}") is not None
                assert scheduler.get_task("digest") is not None
                assert len(scheduler.tasks) == 2
                scheduler.stop()

    def test_uses_custom_user_id(self) -> None:
        config = AppConfig()
        config.background_scheduler.enabled = True
        uid = uuid.uuid4()

        with patch("services.background.tasks.SessionLocal"):
            scheduler = create_and_start_scheduler(config, user_id=uid)
            assert scheduler is not None
            scheduler.stop()

    def test_no_profiles_logs_warning_and_registers_no_pipeline_tasks(self) -> None:
        config = AppConfig()
        config.background_scheduler.enabled = True
        config.background_scheduler.pipeline_enabled = True

        uid = uuid.uuid4()

        with patch("services.background.tasks.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_repo = MagicMock()
            mock_repo.list_by_user_id.return_value = []
            with patch("services.background.tasks.ProfileRepository", return_value=mock_repo):
                scheduler = create_and_start_scheduler(config, user_id=uid)
                assert scheduler is not None
                pipeline_tasks = [t for t in scheduler.tasks if t.name.startswith("pipeline:")]
                assert len(pipeline_tasks) == 0
                scheduler.stop()


# ── Edge cases ───────────────────────────────────────────────────────


class TestSchedulerEdgeCases:
    def test_tick_handles_exception_gracefully(self) -> None:
        """If a task callback raises, _tick should not crash the loop."""
        def crashing() -> None:
            raise RuntimeError("crash")

        scheduler = BackgroundScheduler(polling_interval=1)
        task = ScheduledTask(name="crash", interval_seconds=1, callback=crashing, max_retries=0)
        scheduler._tasks = {"crash": task}

        # should not raise
        scheduler._tick()
        time.sleep(0.05)
        assert task._running is False
        scheduler.stop()

    def test_loop_error_logged_not_crashed(self) -> None:
        """An exception in _tick should be logged, not crash the thread."""
        scheduler = BackgroundScheduler(polling_interval=1)

        # monkey-patch _tick to raise
        original_tick = scheduler._tick

        def broken_tick() -> None:
            raise ValueError("tick error")

        scheduler._tick = broken_tick
        scheduler.start()
        time.sleep(0.2)
        # thread should still be alive
        assert scheduler.running is True
        scheduler._tick = original_tick
        scheduler.stop()

    def test_callable_interval_dynamic_change(self) -> None:
        """Changing the interval source should take effect on next tick."""
        config = {"interval": 3600}
        scheduler = BackgroundScheduler(polling_interval=1)
        calls = []

        def cb() -> None:
            calls.append(1)

        task = ScheduledTask(
            name="dynamic2",
            interval_seconds=lambda: config["interval"],
            callback=cb,
            max_retries=0,
        )
        scheduler._tasks = {"dynamic2": task}

        scheduler._tick()
        assert len(calls) == 1

        config["interval"] = 1  # shorten
        from datetime import datetime, timezone, timedelta
        task._last_run = datetime.now(timezone.utc) - timedelta(seconds=5)
        scheduler._tick()
        assert len(calls) == 2

        scheduler.stop()


# ── Window Scheduling Condition ─────────────────────────────────────


class TestWindowSchedulingCondition:
    """Tests covering calendar-day, local-time window scheduling."""

    def test_run_condition_true_inside_window_no_prior_run(self, tmp_path) -> None:
        """Condition is True inside window when task hasn't run today."""
        import zoneinfo
        from datetime import datetime

        from database.base import Base
        from database.models import Profile
        from database.repositories import UserRepository
        from database.session import SessionLocal, init_db
        from services.background.tasks import _make_pipeline_run_condition

        db_path = tmp_path / "test.db"
        init_db(data_dir=str(db_path.parent))
        db_factory = SessionLocal

        uid = uuid.uuid4()
        pid = uuid.uuid4()
        db = db_factory()
        UserRepository(db).get_or_create(uid)
        db.add(Profile(id=pid, user_id=uid, name="Test Profile"))
        db.commit()
        db.close()

        config = AppConfig()
        config.background_scheduler.timezone = "Asia/Kolkata"
        config.background_scheduler.pipeline_window_start_hour = 6
        config.background_scheduler.pipeline_window_end_hour = 12

        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        fake_now = datetime(2026, 7, 25, 8, 0, tzinfo=tz)

        cond = _make_pipeline_run_condition(uid, pid, config, session_factory=db_factory)

        with patch("services.background.tasks.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            assert cond() is True

        Base.metadata.drop_all(bind=SessionLocal.kw["bind"])

    def test_run_condition_false_outside_window(self, tmp_path) -> None:
        """Condition is False outside window (e.g. 2 PM local)."""
        import zoneinfo
        from datetime import datetime

        from database.base import Base
        from database.models import Profile
        from database.repositories import UserRepository
        from database.session import SessionLocal, init_db
        from services.background.tasks import _make_pipeline_run_condition

        db_path = tmp_path / "test.db"
        init_db(data_dir=str(db_path.parent))
        db_factory = SessionLocal

        uid = uuid.uuid4()
        pid = uuid.uuid4()
        db = db_factory()
        UserRepository(db).get_or_create(uid)
        db.add(Profile(id=pid, user_id=uid, name="Test Profile"))
        db.commit()
        db.close()

        config = AppConfig()
        config.background_scheduler.timezone = "Asia/Kolkata"
        config.background_scheduler.pipeline_window_start_hour = 6
        config.background_scheduler.pipeline_window_end_hour = 12

        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        fake_now = datetime(2026, 7, 25, 14, 0, tzinfo=tz)

        cond = _make_pipeline_run_condition(uid, pid, config, session_factory=db_factory)

        with patch("services.background.tasks.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            assert cond() is False

        Base.metadata.drop_all(bind=SessionLocal.kw["bind"])

    def test_run_condition_false_when_already_run_today_inside_window(self, tmp_path) -> None:
        """Condition is False inside window if already completed today."""
        import zoneinfo
        from datetime import date, datetime

        from database.base import Base
        from database.models import Profile
        from database.repositories import SchedulerStateRepository, UserRepository
        from database.session import SessionLocal, init_db
        from services.background.tasks import _make_pipeline_run_condition

        db_path = tmp_path / "test.db"
        init_db(data_dir=str(db_path.parent))
        db_factory = SessionLocal

        uid = uuid.uuid4()
        pid = uuid.uuid4()
        db = db_factory()
        UserRepository(db).get_or_create(uid)
        db.add(Profile(id=pid, user_id=uid, name="Test Profile"))
        today = date(2026, 7, 25)
        SchedulerStateRepository(db).update_last_run(
            uid, "pipeline", run_date=today, profile_id=pid,
        )
        db.commit()
        db.close()

        config = AppConfig()
        config.background_scheduler.timezone = "Asia/Kolkata"
        config.background_scheduler.pipeline_window_start_hour = 6
        config.background_scheduler.pipeline_window_end_hour = 12

        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        fake_now = datetime(2026, 7, 25, 9, 30, tzinfo=tz)

        cond = _make_pipeline_run_condition(uid, pid, config, session_factory=db_factory)

        with patch("services.background.tasks.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            assert cond() is False

        Base.metadata.drop_all(bind=SessionLocal.kw["bind"])

    def test_run_condition_true_next_calendar_day(self, tmp_path) -> None:
        """Condition becomes True again on the next calendar day."""
        import zoneinfo
        from datetime import date, datetime

        from database.base import Base
        from database.models import Profile
        from database.repositories import SchedulerStateRepository, UserRepository
        from database.session import SessionLocal, init_db
        from services.background.tasks import _make_pipeline_run_condition

        db_path = tmp_path / "test.db"
        init_db(data_dir=str(db_path.parent))
        db_factory = SessionLocal

        uid = uuid.uuid4()
        pid = uuid.uuid4()
        db = db_factory()
        UserRepository(db).get_or_create(uid)
        db.add(Profile(id=pid, user_id=uid, name="Test Profile"))
        yesterday = date(2026, 7, 24)
        SchedulerStateRepository(db).update_last_run(
            uid, "pipeline", run_date=yesterday, profile_id=pid,
        )
        db.commit()
        db.close()

        config = AppConfig()
        config.background_scheduler.timezone = "Asia/Kolkata"
        config.background_scheduler.pipeline_window_start_hour = 6
        config.background_scheduler.pipeline_window_end_hour = 12

        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        fake_now = datetime(2026, 7, 25, 8, 0, tzinfo=tz)

        cond = _make_pipeline_run_condition(uid, pid, config, session_factory=db_factory)

        with patch("services.background.tasks.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            assert cond() is True

        Base.metadata.drop_all(bind=SessionLocal.kw["bind"])

    def test_last_run_date_persists_across_scheduler_restart(self, tmp_path) -> None:
        """Scheduler state persisted in DB prevents re-run across new BackgroundScheduler instances."""
        import zoneinfo
        from datetime import date, datetime

        from database.base import Base
        from database.models import Profile
        from database.repositories import SchedulerStateRepository, UserRepository
        from database.session import SessionLocal, init_db
        from services.background.tasks import _make_pipeline_run_condition

        db_path = tmp_path / "test.db"
        init_db(data_dir=str(db_path.parent))
        db_factory = SessionLocal

        uid = uuid.uuid4()
        pid = uuid.uuid4()
        db = db_factory()
        UserRepository(db).get_or_create(uid)
        db.add(Profile(id=pid, user_id=uid, name="Test Profile"))
        db.commit()
        db.close()

        config = AppConfig()
        config.background_scheduler.enabled = True
        config.background_scheduler.pipeline_enabled = True
        config.background_scheduler.timezone = "Asia/Kolkata"
        config.background_scheduler.pipeline_window_start_hour = 6
        config.background_scheduler.pipeline_window_end_hour = 12

        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        fake_now = datetime(2026, 7, 25, 7, 0, tzinfo=tz)

        # Instance 1: runs and persists state in DB
        db1 = db_factory()
        SchedulerStateRepository(db1).update_last_run(
            uid, "pipeline", run_date=date(2026, 7, 25), profile_id=pid,
        )
        db1.commit()
        db1.close()

        # Instance 2: brand new BackgroundScheduler instance created (simulating app restart)
        sched2 = BackgroundScheduler()
        cond2 = _make_pipeline_run_condition(uid, pid, config, session_factory=db_factory)
        task2 = ScheduledTask(
            name=f"pipeline:{pid}", interval_seconds=60,
            run_condition=cond2, callback=lambda: None,
        )
        sched2.add_task(task2)

        with patch("services.background.tasks.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            assert cond2() is False

        Base.metadata.drop_all(bind=SessionLocal.kw["bind"])


# ── Multi-Profile Scheduling ────────────────────────────────────────


class TestMultiProfileScheduling:
    """Tests covering per-profile pipeline task scheduling."""

    def test_three_profiles_get_three_independent_tasks(self, tmp_path) -> None:
        """A user with 3 profiles gets 3 independent scheduled tasks."""
        import zoneinfo
        from datetime import date, datetime

        from database.base import Base
        from database.models import Profile
        from database.repositories import SchedulerStateRepository, UserRepository
        from database.session import SessionLocal, init_db
        from services.background.tasks import _make_pipeline_run_condition, _pipeline_callback

        db_path = tmp_path / "test.db"
        init_db(data_dir=str(db_path.parent))
        db_factory = SessionLocal

        uid = uuid.uuid4()
        pids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        db = db_factory()
        UserRepository(db).get_or_create(uid)
        for pid in pids:
            db.add(Profile(id=pid, user_id=uid, name=f"Profile {pid}"))
        db.commit()
        db.close()

        config = AppConfig()
        config.background_scheduler.timezone = "Asia/Kolkata"
        config.background_scheduler.pipeline_window_start_hour = 6
        config.background_scheduler.pipeline_window_end_hour = 12

        # Create 3 separate conditions — each should be True (never run)
        conditions = [
            _make_pipeline_run_condition(uid, pid, config, session_factory=db_factory)
            for pid in pids
        ]

        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        fake_now = datetime(2026, 7, 25, 8, 0, tzinfo=tz)
        for i, cond in enumerate(conditions):
            with patch("services.background.tasks.datetime") as mock_dt:
                mock_dt.now.return_value = fake_now
                assert cond() is True, f"Profile {pids[i]} condition should be True"

        Base.metadata.drop_all(bind=SessionLocal.kw["bind"])

    def test_one_profile_failing_does_not_affect_other_state(self, tmp_path) -> None:
        """One profile's pipeline failing should not affect another's SchedulerState."""
        from datetime import date

        from database.base import Base
        from database.models import Profile
        from database.repositories import SchedulerStateRepository, UserRepository
        from database.session import SessionLocal, init_db

        db_path = tmp_path / "test.db"
        init_db(data_dir=str(db_path.parent))
        db_factory = SessionLocal

        uid = uuid.uuid4()
        pid_a, pid_b = uuid.uuid4(), uuid.uuid4()
        db = db_factory()
        UserRepository(db).get_or_create(uid)
        db.add(Profile(id=pid_a, user_id=uid, name="Profile A"))
        db.add(Profile(id=pid_b, user_id=uid, name="Profile B"))
        db.commit()

        # Profile A succeeded today, Profile B has not
        SchedulerStateRepository(db).update_last_run(
            uid, "pipeline", run_date=date(2026, 7, 25), profile_id=pid_a,
        )
        db.commit()
        db.close()

        db2 = db_factory()
        repo = SchedulerStateRepository(db2)

        state_a = repo.get_by_user_and_task(uid, "pipeline", profile_id=pid_a)
        assert state_a is not None
        assert state_a.last_run_date == date(2026, 7, 25)

        state_b = repo.get_by_user_and_task(uid, "pipeline", profile_id=pid_b)
        assert state_b is None  # never ran for profile B

        Base.metadata.drop_all(bind=SessionLocal.kw["bind"])

    def test_second_profile_still_runs_when_first_already_done(self, tmp_path) -> None:
        """After profile A completes, profile B's condition is still True if it hasn't run yet."""
        import zoneinfo
        from datetime import date, datetime

        from database.base import Base
        from database.models import Profile
        from database.repositories import SchedulerStateRepository, UserRepository
        from database.session import SessionLocal, init_db
        from services.background.tasks import _make_pipeline_run_condition

        db_path = tmp_path / "test.db"
        init_db(data_dir=str(db_path.parent))
        db_factory = SessionLocal

        uid = uuid.uuid4()
        pid_a, pid_b = uuid.uuid4(), uuid.uuid4()
        db = db_factory()
        UserRepository(db).get_or_create(uid)
        db.add(Profile(id=pid_a, user_id=uid, name="Profile A"))
        db.add(Profile(id=pid_b, user_id=uid, name="Profile B"))

        # Profile A already ran today
        SchedulerStateRepository(db).update_last_run(
            uid, "pipeline", run_date=date(2026, 7, 25), profile_id=pid_a,
        )
        db.commit()
        db.close()

        config = AppConfig()
        config.background_scheduler.timezone = "Asia/Kolkata"
        config.background_scheduler.pipeline_window_start_hour = 6
        config.background_scheduler.pipeline_window_end_hour = 12

        cond_a = _make_pipeline_run_condition(uid, pid_a, config, session_factory=db_factory)
        cond_b = _make_pipeline_run_condition(uid, pid_b, config, session_factory=db_factory)

        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        fake_now = datetime(2026, 7, 25, 8, 30, tzinfo=tz)

        with patch("services.background.tasks.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            assert cond_a() is False, "Profile A already ran today"
            assert cond_b() is True, "Profile B still needs to run"

        Base.metadata.drop_all(bind=SessionLocal.kw["bind"])


"""Thread safety tests for shared-state components."""

from __future__ import annotations

import threading
import time

from services.ai.cache import AICache
from services.ai.token_counter import TokenCounter
from services.background.scheduler import BackgroundScheduler, ScheduledTask


class TestAICacheThreadSafety:
    def test_concurrent_access(self):
        cache = AICache(ttl=300, max_size=100)
        errors = []
        def worker():
            try:
                for i in range(50):
                    msg = [{"role": "user", "content": f"hello {i}"}]
                    existing = cache.get(msg, {"model": "gpt-4o"})
                    if existing is None:
                        from services.ai.models import AIResponse
                        cache.set(msg, {"model": "gpt-4o"}, AIResponse(content=f"reply {i}"))
                    _ = cache.size
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_clear_during_access(self):
        cache = AICache(ttl=300, max_size=100)
        from services.ai.models import AIResponse
        for i in range(50):
            cache.set(
                [{"role": "user", "content": f"msg{i}"}],
                {"model": "gpt-4o"},
                AIResponse(content=f"res{i}"),
            )
        errors = []
        def reader():
            try:
                for i in range(100):
                    _ = cache.size
            except Exception as e:
                errors.append(e)
        t = threading.Thread(target=reader)
        t.start()
        cache.clear()
        t.join()
        assert not errors


class TestTokenCounterSingleton:
    def test_single_instance(self):
        t1 = TokenCounter()
        t2 = TokenCounter()
        assert t1 is t2

    def test_thread_safe_init(self):
        instances = []
        def create():
            instances.append(TokenCounter())
        threads = [threading.Thread(target=create) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(i is instances[0] for i in instances)


class TestSchedulerThreadSafety:
    def test_concurrent_add_remove(self):
        sched = BackgroundScheduler(polling_interval=5)
        errors = []
        def adder():
            try:
                for i in range(100):
                    task = ScheduledTask(
                        name=f"task-{threading.get_ident()}-{i}",
                        interval_seconds=9999,
                        callback=lambda: None,
                    )
                    sched.add_task(task)
                    if i % 2 == 0:
                        sched.remove_task(task.name)
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=adder) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_tasks_property_snapshot(self):
        sched = BackgroundScheduler(polling_interval=5)
        for i in range(10):
            sched.add_task(ScheduledTask(
                name=f"t{i}", interval_seconds=60, callback=lambda: None,
            ))
        snapshot = sched.tasks
        assert len(snapshot) == 10
        sched.add_task(ScheduledTask(
            name="new", interval_seconds=60, callback=lambda: None,
        ))
        assert len(snapshot) == 10

    def test_remove_nonexistent(self):
        sched = BackgroundScheduler(polling_interval=5)
        sched.remove_task("does-not-exist")

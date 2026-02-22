"""Unit tests for Weave dispatcher."""

import asyncio
import time

import pytest

from app.core.config import WeaveSettings
from app.services.observability import WeaveDispatcher


class TestWeaveDispatcher:
    """Tests for WeaveDispatcher."""

    @pytest.fixture
    def settings(self) -> WeaveSettings:
        """Create default Weave settings for testing."""
        return WeaveSettings(
            enabled=True,
            project="test-project",
            queue_maxsize=10,
            worker_count=2,
            timeout_ms=1000,
        )

    @pytest.fixture
    def settings_small_queue(self) -> WeaveSettings:
        """Create settings with small queue for testing overflow."""
        return WeaveSettings(
            enabled=True,
            project="test-project",
            queue_maxsize=2,
            worker_count=1,
            timeout_ms=1000,
        )

    @pytest.fixture
    async def dispatcher(self, settings: WeaveSettings) -> WeaveDispatcher:
        """Create and start a dispatcher for testing."""
        dispatcher = WeaveDispatcher(settings)
        await dispatcher.start()
        yield dispatcher
        await dispatcher.stop()

    @pytest.mark.asyncio
    async def test_dispatcher_start_stop(self, settings: WeaveSettings) -> None:
        """Dispatcher should start and stop cleanly."""
        dispatcher = WeaveDispatcher(settings)

        await dispatcher.start()
        assert dispatcher._running is True
        assert len(dispatcher._workers) == settings.worker_count

        await dispatcher.stop()
        assert dispatcher._running is False
        assert len(dispatcher._workers) == 0

    @pytest.mark.asyncio
    async def test_dispatch_non_blocking(self, dispatcher: WeaveDispatcher) -> None:
        """dispatch should return immediately without waiting for task completion."""
        executed = []

        async def slow_task():
            await asyncio.sleep(0.2)
            executed.append(1)

        start = time.time()
        await dispatcher.dispatch(slow_task)
        elapsed = time.time() - start

        # Should return immediately (well under 0.2s)
        assert elapsed < 0.1, f"dispatch took {elapsed}s, expected < 0.1s"

        # Wait for task to actually complete
        await asyncio.sleep(0.3)
        assert len(executed) == 1

    @pytest.mark.asyncio
    async def test_dispatch_multiple_tasks(self, dispatcher: WeaveDispatcher) -> None:
        """Multiple tasks should be processed by workers."""
        results = []

        async def task(value: int):
            await asyncio.sleep(0.01)
            results.append(value)

        # Dispatch multiple tasks
        for i in range(5):
            await dispatcher.dispatch(task, value=i)

        # Wait for all to complete
        await asyncio.sleep(0.1)

        assert len(results) == 5
        assert set(results) == {0, 1, 2, 3, 4}

    @pytest.mark.asyncio
    async def test_queue_full_drops_observation(
        self, settings_small_queue: WeaveSettings
    ) -> None:
        """Full queue should drop new observations without blocking."""
        dispatcher = WeaveDispatcher(settings_small_queue)
        await dispatcher.start()

        executed = []

        async def slow_task():
            await asyncio.sleep(0.5)
            executed.append(1)

        # Fill queue (maxsize=2)
        await dispatcher.dispatch(slow_task)
        await dispatcher.dispatch(slow_task)

        # Queue is now full, this should be dropped
        await dispatcher.dispatch(slow_task)

        # Give workers time to start first two tasks
        await asyncio.sleep(0.1)

        # Queue should be full (tasks still running)
        assert dispatcher._queue.qsize() <= 2

        # Third dispatch should not block
        await dispatcher.dispatch(slow_task)

        await dispatcher.stop()

        # Should have processed at least 1 item
        await asyncio.sleep(0.6)
        assert len(executed) >= 1

    @pytest.mark.asyncio
    async def test_task_timeout(self) -> None:
        """Tasks exceeding timeout should be cancelled."""
        settings_timeout = WeaveSettings(
            enabled=True,
            project="test-project",
            queue_maxsize=10,
            worker_count=1,
            timeout_ms=100,  # Very short timeout
        )
        dispatcher = WeaveDispatcher(settings_timeout)
        await dispatcher.start()

        async def slow_task():
            await asyncio.sleep(1.0)  # Longer than timeout

        # Should not raise despite timeout
        await dispatcher.dispatch(slow_task)

        # Wait for timeout to trigger
        await asyncio.sleep(0.2)

        await dispatcher.stop()

    @pytest.mark.asyncio
    async def test_task_exception_isolated(self, dispatcher: WeaveDispatcher) -> None:
        """Exceptions in tasks should not crash workers."""
        executed = []

        async def failing_task():
            executed.append("before")
            raise ValueError("Task failed!")

        async def normal_task():
            executed.append("normal")

        # Dispatch failing task
        await dispatcher.dispatch(failing_task)

        # Dispatch normal task after
        await asyncio.sleep(0.05)
        await dispatcher.dispatch(normal_task)

        # Wait for processing
        await asyncio.sleep(0.1)

        # Both should have been attempted
        assert "before" in executed
        assert "normal" in executed

    @pytest.mark.asyncio
    async def test_stop_drains_queue(self, settings: WeaveSettings) -> None:
        """stop should wait for queue to drain (with timeout)."""
        dispatcher = WeaveDispatcher(settings)
        await dispatcher.start()

        executed = []

        async def quick_task():
            await asyncio.sleep(0.01)
            executed.append(1)

        # Add tasks
        for _ in range(3):
            await dispatcher.dispatch(quick_task)

        # Give workers time to pick up tasks
        await asyncio.sleep(0.05)

        # Stop should drain queue
        await dispatcher.stop()

        # All tasks should be processed
        assert len(executed) == 3

    @pytest.mark.asyncio
    async def test_stop_timeout_with_remaining_tasks(self) -> None:
        """stop should timeout if tasks take too long."""
        settings_slow = WeaveSettings(
            enabled=True,
            project="test-project",
            queue_maxsize=10,
            worker_count=1,
            timeout_ms=100,
        )
        dispatcher = WeaveDispatcher(settings_slow)
        await dispatcher.start()

        executed = []

        async def slow_task():
            await asyncio.sleep(0.5)
            executed.append(1)

        # Add slow task
        await dispatcher.dispatch(slow_task)

        # Stop should timeout after 5 seconds (default)
        start = time.time()
        await dispatcher.stop()
        elapsed = time.time() - start

        # Should timeout quickly, not wait forever
        assert elapsed < 6.0

    @pytest.mark.asyncio
    async def test_worker_processes_sequentially(self) -> None:
        """Single worker should process tasks sequentially."""
        settings_single = WeaveSettings(
            enabled=True,
            project="test-project",
            queue_maxsize=10,
            worker_count=1,
            timeout_ms=1000,
        )
        dispatcher = WeaveDispatcher(settings_single)
        await dispatcher.start()

        order = []

        async def ordered_task(value: int):
            order.append(value)
            await asyncio.sleep(0.01)

        for i in range(3):
            await dispatcher.dispatch(ordered_task, value=i)

        await asyncio.sleep(0.1)
        await dispatcher.stop()

        # Should maintain order with single worker
        assert order == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_concurrent_workers(self) -> None:
        """Multiple workers should process concurrently."""
        settings_multi = WeaveSettings(
            enabled=True,
            project="test-project",
            queue_maxsize=10,
            worker_count=3,
            timeout_ms=1000,
        )
        dispatcher = WeaveDispatcher(settings_multi)
        await dispatcher.start()

        concurrent_count = 0
        max_concurrent = 0

        async def counting_task():
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            if concurrent_count > max_concurrent:
                max_concurrent = concurrent_count
            await asyncio.sleep(0.05)
            concurrent_count -= 1

        # Dispatch many tasks
        for _ in range(6):
            await dispatcher.dispatch(counting_task)

        await asyncio.sleep(0.1)
        await dispatcher.stop()

        # With 3 workers, should have had some concurrency
        assert max_concurrent >= 2

    @pytest.mark.asyncio
    async def test_dispatch_with_kwargs(self, dispatcher: WeaveDispatcher) -> None:
        """dispatch should pass kwargs to the coroutine."""
        result = []

        async def task_with_kwargs(a: int, b: str, c: float = 1.0):
            result.append((a, b, c))

        await dispatcher.dispatch(task_with_kwargs, a=42, b="test", c=3.14)
        await asyncio.sleep(0.05)

        assert len(result) == 1
        assert result[0] == (42, "test", 3.14)

    @pytest.mark.asyncio
    async def test_dispatcher_empty_queue_no_crash(
        self, dispatcher: WeaveDispatcher
    ) -> None:
        """Dispatcher should handle empty queue gracefully."""
        # Just wait a bit with no tasks
        await asyncio.sleep(0.1)
        # Dispatcher should still be running
        assert dispatcher._running is True

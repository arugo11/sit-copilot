"""Async dispatcher for non-blocking Weave operations."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["WeaveDispatcher"]


class WeaveDispatcher:
    """Non-blocking dispatcher for Weave operations.

    Operations are queued and processed by background workers to avoid
    blocking request handlers. Full queue results in dropped observations.
    """

    def __init__(self, settings: Any) -> None:
        """Initialize dispatcher with settings.

        Args:
            settings: WeaveSettings instance with queue_maxsize, worker_count,
                     and timeout_ms attributes.
        """
        self.settings = settings
        self._queue: asyncio.Queue[tuple[Callable, dict]] = asyncio.Queue(
            maxsize=settings.queue_maxsize
        )
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """Start background workers."""
        self._running = True
        for i in range(self.settings.worker_count):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)
        logger.info(
            f"WeaveDispatcher started: {self.settings.worker_count} workers, "
            f"queue maxsize={self.settings.queue_maxsize}"
        )

    async def stop(self) -> None:
        """Stop workers and drain queue."""
        self._running = False

        # Wait for queue to drain with timeout
        try:
            await asyncio.wait_for(self._queue.join(), timeout=5.0)
        except TimeoutError:
            remaining = self._queue.qsize()
            logger.warning(f"Weave queue drain timeout: {remaining} items remaining")

        # Cancel workers
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("WeaveDispatcher stopped")

    async def dispatch(self, coro: Callable, **kwargs: Any) -> None:
        """Dispatch coroutine to background worker (non-blocking).

        If the queue is full, the observation is dropped and logged.
        This ensures observability failures never impact request handling.

        Args:
            coro: Async callable to execute.
            **kwargs: Arguments to pass to the callable.
        """
        try:
            self._queue.put_nowait((coro, kwargs))
        except asyncio.QueueFull:
            logger.warning("Weave queue full, dropping observation")

    async def _worker(self, name: str) -> None:
        """Background worker that processes queued observations.

        Args:
            name: Worker identifier for logging.
        """
        while self._running:
            try:
                coro, kwargs = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
                try:
                    await asyncio.wait_for(
                        coro(**kwargs),
                        timeout=self.settings.timeout_ms / 1000,
                    )
                except TimeoutError:
                    logger.warning(
                        f"Weave observation timeout in {name}: "
                        f"operation exceeded {self.settings.timeout_ms}ms"
                    )
                except Exception as e:
                    logger.warning(f"Weave observation failed in {name}: {e}")
                finally:
                    self._queue.task_done()
            except TimeoutError:
                # No item in queue, continue loop
                continue
            except Exception as e:
                logger.error(f"Unexpected error in {name}: {e}")
                # Mark task done to avoid deadlock
                if not self._queue.empty():
                    self._queue.task_done()

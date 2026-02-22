"""Observed wrapper for Lecture Summary service with Weave tracking."""

from __future__ import annotations

import logging
from time import perf_counter

from app.schemas.lecture import LectureSummaryLatestResponse
from app.services.lecture_summary_service import LectureSummaryService
from app.services.observability import WeaveObserverService

__all__ = [
    "ObservedLectureSummaryService",
    "ObservedLectureSummaryServiceError",
]

logger = logging.getLogger(__name__)


class ObservedLectureSummaryServiceError(Exception):
    """Raised when observed summary service wrapper fails."""


class ObservedLectureSummaryService:
    """Observed wrapper for Lecture Summary service."""

    def __init__(
        self,
        inner: LectureSummaryService,
        observer: WeaveObserverService,
    ) -> None:
        """Initialize observed summary service.

        Args:
            inner: Underlying summary service implementation
            observer: Weave observer service for tracking
        """
        self._inner = inner
        self._observer = observer

    async def get_latest_summary(
        self,
        session_id: str,
        user_id: str,
    ) -> LectureSummaryLatestResponse:
        """Get latest summary with observation tracking."""
        start_time = perf_counter()

        # Call inner service
        result = await self._inner.get_latest_summary(session_id, user_id)

        latency_ms = int((perf_counter() - start_time) * 1000)

        # Track summary retrieval
        await self._observer.track_llm_call(
            provider="summary-service",
            model="get_latest",
            prompt=f"session: {session_id}",
            response=result.summary[:500] if result.summary else "",
            latency_ms=latency_ms,
            metadata={
                "session_id": session_id,
                "window_start_ms": result.window_start_ms,
                "window_end_ms": result.window_end_ms,
                "status": result.status,
                "key_terms_count": len(result.key_terms),
                "evidence_count": len(result.evidence),
            },
        )

        return result

    async def rebuild_windows(
        self,
        session_id: str,
        user_id: str,
    ) -> int:
        """Rebuild summary windows with observation tracking."""
        start_time = perf_counter()

        # Call inner service
        window_count = await self._inner.rebuild_windows(session_id, user_id)

        latency_ms = int((perf_counter() - start_time) * 1000)

        # Track rebuild operation
        await self._observer.track_llm_call(
            provider="summary-service",
            model="rebuild_windows",
            prompt=f"session: {session_id}",
            response=f"rebuilt {window_count} windows",
            latency_ms=latency_ms,
            metadata={
                "session_id": session_id,
                "window_count": window_count,
            },
        )

        return window_count

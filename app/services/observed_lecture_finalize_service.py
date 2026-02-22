"""Observed wrapper for Lecture Finalize service with Weave tracking."""

from __future__ import annotations

import logging
from time import perf_counter

from app.schemas.lecture import LectureSessionFinalizeResponse
from app.services.lecture_finalize_service import LectureFinalizeService
from app.services.observability import WeaveObserverService

__all__ = [
    "ObservedLectureFinalizeService",
    "ObservedLectureFinalizeServiceError",
]

logger = logging.getLogger(__name__)


class ObservedLectureFinalizeServiceError(Exception):
    """Raised when observed finalize service wrapper fails."""


class ObservedLectureFinalizeService:
    """Observed wrapper for lecture session finalization."""

    def __init__(
        self,
        inner: LectureFinalizeService,
        observer: WeaveObserverService,
    ) -> None:
        """Initialize observed finalize service.

        Args:
            inner: Underlying finalize service implementation
            observer: Weave observer service for tracking
        """
        self._inner = inner
        self._observer = observer

    async def finalize(
        self,
        session_id: str,
        build_qa_index: bool,
    ) -> LectureSessionFinalizeResponse:
        """Finalize lecture session with observation tracking."""
        start_time = perf_counter()

        # Call inner service
        result = await self._inner.finalize(session_id, build_qa_index)

        latency_ms = int((perf_counter() - start_time) * 1000)

        # Track session end with stats
        await self._observer.track_llm_call(
            provider="system",
            model="session_finalize",
            prompt=f"session: {session_id}, build_qa_index: {build_qa_index}",
            response=f"finalized with {result.stats.speech_events} speech, "
            f"{result.stats.visual_events} visual events",
            latency_ms=latency_ms,
            metadata={
                "session_id": session_id,
                "status": result.status,
                "note_generated": result.note_generated,
                "qa_index_built": result.qa_index_built,
                "stats": {
                    "speech_events": result.stats.speech_events,
                    "visual_events": result.stats.visual_events,
                    "summary_windows": result.stats.summary_windows,
                    "lecture_chunks": result.stats.lecture_chunks,
                },
            },
        )

        return result

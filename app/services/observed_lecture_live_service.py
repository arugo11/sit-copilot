"""Observed wrapper for Lecture Live service with Weave tracking."""

from __future__ import annotations

import logging
from time import perf_counter

from app.schemas.lecture import (
    LectureSessionLangModeUpdateResponse,
    LectureSessionStartRequest,
    LectureSessionStartResponse,
    SpeechChunkAuditApplyResponse,
    SpeechChunkIngestRequest,
    SpeechChunkIngestResponse,
    VisualEventIngestRequest,
    VisualEventIngestResponse,
)
from app.services.lecture_live_service import (
    LectureLiveService,
)
from app.services.observability import WeaveObserverService

__all__ = [
    "ObservedLectureLiveService",
    "ObservedLectureLiveServiceError",
]

logger = logging.getLogger(__name__)


class ObservedLectureLiveServiceError(Exception):
    """Raised when observed live service wrapper fails."""


class ObservedLectureLiveService:
    """Observed wrapper for Lecture Live service with multimodal tracking."""

    def __init__(
        self,
        inner: LectureLiveService,
        observer: WeaveObserverService,
    ) -> None:
        """Initialize observed live service.

        Args:
            inner: Underlying live service implementation
            observer: Weave observer service for tracking
        """
        self._inner = inner
        self._observer = observer

    async def start_session(
        self,
        request: LectureSessionStartRequest,
    ) -> LectureSessionStartResponse:
        """Start a lecture session with observation tracking."""
        start_time = perf_counter()
        response = await self._inner.start_session(request)
        latency_ms = int((perf_counter() - start_time) * 1000)

        # Track session start
        await self._observer.track_llm_call(
            provider="system",
            model="session_start",
            prompt=f"session_start: {request.course_name}",
            response=response.session_id,
            latency_ms=latency_ms,
            metadata={
                "course_id": request.course_id,
                "lang_mode": request.lang_mode,
                "camera_enabled": request.camera_enabled,
            },
        )

        return response

    async def ingest_speech_chunk(
        self,
        request: SpeechChunkIngestRequest,
    ) -> SpeechChunkIngestResponse:
        """Persist a speech chunk with observation tracking."""
        # Call inner service
        response = await self._inner.ingest_speech_chunk(request)

        # Track speech event (metadata only for audio)
        await self._observer.track_speech_event(
            session_id=request.session_id,
            start_ms=request.start_ms,
            end_ms=request.end_ms,
            text=request.text,
            original_text=None,
            confidence=request.confidence,
            is_final=request.is_final,
            speaker=request.speaker or "",
        )

        return response

    async def ingest_visual_event(
        self,
        request: VisualEventIngestRequest,
        image_bytes: bytes,
    ) -> VisualEventIngestResponse:
        """Persist a visual event with observation tracking."""
        # Call inner service
        response = await self._inner.ingest_visual_event(request, image_bytes)

        # Track visual event with image preview
        await self._observer.track_ocr_with_image(
            session_id=request.session_id,
            timestamp_ms=request.timestamp_ms,
            source=request.source,
            ocr_text=response.ocr_text,
            ocr_confidence=response.ocr_confidence,
            quality=response.quality,
            change_score=request.change_score,
            image_bytes=image_bytes,
        )

        return response

    async def update_lang_mode(
        self,
        session_id: str,
        lang_mode: str,
    ) -> LectureSessionLangModeUpdateResponse:
        """Update language mode with observation tracking."""
        start_time = perf_counter()
        response = await self._inner.update_lang_mode(session_id, lang_mode)
        latency_ms = int((perf_counter() - start_time) * 1000)

        # Track lang mode update
        await self._observer.track_llm_call(
            provider="system",
            model="lang_mode_update",
            prompt=f"session: {session_id}, mode: {lang_mode}",
            response=response.lang_mode,
            latency_ms=latency_ms,
        )

        return response

    async def audit_and_apply_speech_chunk(
        self,
        *,
        session_id: str,
        event_id: str,
    ) -> SpeechChunkAuditApplyResponse:
        """Audit and apply speech chunk with observation tracking."""
        start_time = perf_counter()
        response = await self._inner.audit_and_apply_speech_chunk(
            session_id=session_id,
            event_id=event_id,
        )
        latency_ms = int((perf_counter() - start_time) * 1000)

        # Track ASR correction event
        await self._observer.track_llm_call(
            provider="azure-openai",
            model="asr_correction",
            prompt=response.original_text,
            response=response.corrected_text,
            latency_ms=latency_ms,
            metadata={
                "session_id": session_id,
                "event_id": event_id,
                "updated": response.updated,
                "review_status": response.review_status,
                "was_corrected": response.was_corrected,
                "retry_count": response.retry_count,
            },
        )

        return response

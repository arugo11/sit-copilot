"""Lecture live service for session lifecycle and event ingestion."""

import logging
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.visual_event import VisualEvent
from app.schemas.lecture import (
    LectureSessionStartRequest,
    LectureSessionStartResponse,
    SpeechChunkIngestRequest,
    SpeechChunkIngestResponse,
    VisualEventIngestRequest,
    VisualEventIngestResponse,
    VisualEventQuality,
)
from app.services.vision_ocr_service import (
    NoopVisionOCRService,
    VisionOCRResult,
    VisionOCRService,
    VisionOCRServiceError,
)

__all__ = [
    "LectureLiveService",
    "LectureSessionInactiveError",
    "LectureSessionNotFoundError",
    "SqlAlchemyLectureLiveService",
]

SESSION_ID_PREFIX = "lec"
GOOD_OCR_CONFIDENCE_THRESHOLD = 0.8
WARN_OCR_CONFIDENCE_THRESHOLD = 0.5
logger = logging.getLogger(__name__)


class LectureSessionNotFoundError(Exception):
    """Raised when speech ingestion targets an unknown session."""


class LectureSessionInactiveError(Exception):
    """Raised when speech ingestion targets a non-active session."""


class LectureLiveService(Protocol):
    """Interface for lecture live operations."""

    async def start_session(
        self,
        request: LectureSessionStartRequest,
    ) -> LectureSessionStartResponse:
        """Start a lecture session and persist it."""
        ...

    async def ingest_speech_chunk(
        self,
        request: SpeechChunkIngestRequest,
    ) -> SpeechChunkIngestResponse:
        """Persist a finalized speech chunk for an active session."""
        ...

    async def ingest_visual_event(
        self,
        request: VisualEventIngestRequest,
        image_bytes: bytes,
    ) -> VisualEventIngestResponse:
        """Persist an OCR visual event for an active session."""
        ...


class SqlAlchemyLectureLiveService:
    """SQLAlchemy implementation of lecture live operations."""

    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        vision_ocr_service: VisionOCRService | None = None,
    ) -> None:
        self._db = db
        self._user_id = user_id
        self._vision_ocr_service = vision_ocr_service or NoopVisionOCRService()

    async def start_session(
        self,
        request: LectureSessionStartRequest,
    ) -> LectureSessionStartResponse:
        """Create a new active lecture session."""
        session_id = self._generate_session_id()
        session = LectureSession(
            id=session_id,
            user_id=self._user_id,
            course_id=request.course_id,
            course_name=request.course_name,
            lang_mode=request.lang_mode,
            status="active",
            camera_enabled=request.camera_enabled,
            slide_roi=request.slide_roi,
            board_roi=request.board_roi,
            consent_acknowledged=request.consent_acknowledged,
        )
        self._db.add(session)
        await self._db.flush()
        return LectureSessionStartResponse(session_id=session.id, status="active")

    async def ingest_speech_chunk(
        self,
        request: SpeechChunkIngestRequest,
    ) -> SpeechChunkIngestResponse:
        """Persist a finalized speech event for an active session."""
        await self._get_active_session(request.session_id)

        speech_event = SpeechEvent(
            session_id=request.session_id,
            start_ms=request.start_ms,
            end_ms=request.end_ms,
            text=request.text,
            confidence=request.confidence,
            is_final=request.is_final,
            speaker=request.speaker,
        )
        self._db.add(speech_event)
        await self._db.flush()

        return SpeechChunkIngestResponse(
            event_id=speech_event.id,
            session_id=request.session_id,
            accepted=True,
        )

    async def ingest_visual_event(
        self,
        request: VisualEventIngestRequest,
        image_bytes: bytes,
    ) -> VisualEventIngestResponse:
        """Persist an OCR visual event for an active session."""
        await self._get_active_session(request.session_id)

        ocr_result = await self._extract_ocr_result(request, image_bytes)
        quality = self._classify_visual_quality(ocr_result.confidence)
        visual_event = VisualEvent(
            session_id=request.session_id,
            timestamp_ms=request.timestamp_ms,
            source=request.source,
            ocr_text=ocr_result.text.strip(),
            ocr_confidence=ocr_result.confidence,
            quality=quality,
            change_score=request.change_score,
            blob_path=None,
        )
        self._db.add(visual_event)
        await self._db.flush()

        return VisualEventIngestResponse(
            event_id=visual_event.id,
            ocr_text=visual_event.ocr_text,
            ocr_confidence=visual_event.ocr_confidence,
            quality=quality,
        )

    async def _get_active_session(self, session_id: str) -> LectureSession:
        """Fetch the session scoped to user and ensure it is active."""
        session_result = await self._db.execute(
            select(LectureSession).where(
                LectureSession.id == session_id,
                LectureSession.user_id == self._user_id,
            )
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            raise LectureSessionNotFoundError(
                f"lecture session not found: {session_id}"
            )

        if session.status != "active":
            raise LectureSessionInactiveError(
                f"lecture session is not active: {session_id}"
            )
        return session

    async def _extract_ocr_result(
        self,
        request: VisualEventIngestRequest,
        image_bytes: bytes,
    ) -> VisionOCRResult:
        """Extract OCR result and degrade safely when provider fails."""
        try:
            return await self._vision_ocr_service.extract_text(
                image_bytes=image_bytes,
                source=request.source,
            )
        except VisionOCRServiceError as exc:
            logger.warning(
                "Vision OCR extraction failed; falling back to bad-quality event. "
                "error_type=%s",
                type(exc).__name__,
            )
            return VisionOCRResult(text="", confidence=0.0)

    @staticmethod
    def _classify_visual_quality(confidence: float) -> VisualEventQuality:
        """Map OCR confidence to quality bands."""
        if confidence >= GOOD_OCR_CONFIDENCE_THRESHOLD:
            return "good"
        if confidence >= WARN_OCR_CONFIDENCE_THRESHOLD:
            return "warn"
        return "bad"

    @staticmethod
    def _generate_session_id() -> str:
        """Generate session ID aligned with SPEC sample style."""
        date_code = datetime.now(UTC).strftime("%Y%m%d")
        suffix = uuid4().hex[:6]
        return f"{SESSION_ID_PREFIX}_{date_code}_{suffix}"

"""Lecture live service for session lifecycle and event ingestion."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy.exc import OperationalError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.user_id import get_user_id_candidates
from app.db.session import is_sqlite_locked_error
from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.speech_review_history import SpeechReviewHistory
from app.models.visual_event import VisualEvent
from app.schemas.lecture import (
    LectureSessionLangModeUpdateResponse,
    LectureSessionStartRequest,
    LectureSessionStartResponse,
    SpeechChunkAuditApplyResponse,
    SpeechChunkIngestRequest,
    SpeechChunkIngestResponse,
    VisualEventIngestRequest,
    VisualEventIngestResponse,
    VisualEventQuality,
)
from app.services.asr_japanese_correction_service import (
    AzureOpenAIJapaneseASRCorrectionService,
    JapaneseASRCorrectionService,
    NoopJapaneseASRCorrectionService,
)
from app.services.asr_hallucination_judge_service import (
    AzureOpenAIJapaneseASRHallucinationJudgeService,
    JapaneseASRHallucinationJudgeService,
    NoopJapaneseASRHallucinationJudgeService,
)
from app.services.asr_subtitle_review_service import SubtitleReviewService
from app.services.vision_ocr_service import (
    AzureVisionOCRService,
    NoopVisionOCRService,
    VisionOCRResult,
    VisionOCRService,
    VisionOCRServiceError,
)

__all__ = [
    "LectureLiveService",
    "LectureSpeechEventNotFoundError",
    "LectureSessionInactiveError",
    "LectureSessionNotFoundError",
    "SqlAlchemyLectureLiveService",
]

SESSION_ID_PREFIX = "lec"
GOOD_OCR_CONFIDENCE_THRESHOLD = 0.8
WARN_OCR_CONFIDENCE_THRESHOLD = 0.5
ACTIVE_SESSION_STATUSES = {"active", "live"}
logger = logging.getLogger(__name__)
WRITE_RETRY_ATTEMPTS = 5
WRITE_RETRY_BASE_DELAY_SECONDS = 0.05


class LectureSessionNotFoundError(Exception):
    """Raised when speech ingestion targets an unknown session."""


class LectureSessionInactiveError(Exception):
    """Raised when speech ingestion targets a non-active session."""


class LectureSpeechEventNotFoundError(Exception):
    """Raised when requested speech event does not exist in session scope."""


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

    async def update_lang_mode(
        self,
        session_id: str,
        lang_mode: str,
    ) -> LectureSessionLangModeUpdateResponse:
        """Update language mode for an active session.

        Note: This only updates the session's lang_mode field.
        Existing summaries are NOT regenerated.
        New summaries will use the updated lang_mode.
        """
        ...

    async def audit_and_apply_speech_chunk(
        self,
        *,
        session_id: str,
        event_id: str,
    ) -> SpeechChunkAuditApplyResponse:
        """Audit a persisted chunk and replace display text in-place."""
        ...


class SqlAlchemyLectureLiveService:
    """SQLAlchemy implementation of lecture live operations."""

    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        vision_ocr_service: VisionOCRService | None = None,
        correction_service: JapaneseASRCorrectionService | None = None,
        judge_service: JapaneseASRHallucinationJudgeService | None = None,
        subtitle_review_service: SubtitleReviewService | None = None,
    ) -> None:
        self._db = db
        self._user_id = user_id
        configured_ocr_service = vision_ocr_service or NoopVisionOCRService()
        if (
            isinstance(configured_ocr_service, NoopVisionOCRService)
            and settings.azure_vision_enabled
            and bool(settings.azure_vision_key.strip())
            and bool(settings.azure_vision_endpoint.strip())
        ):
            self._vision_ocr_service = AzureVisionOCRService(
                endpoint=settings.azure_vision_endpoint,
                api_key=settings.azure_vision_key,
            )
        else:
            self._vision_ocr_service = configured_ocr_service
        configured_correction_service = (
            correction_service or NoopJapaneseASRCorrectionService()
        )
        if (
            isinstance(configured_correction_service, NoopJapaneseASRCorrectionService)
            and settings.azure_openai_enabled
            and settings.lecture_live_asr_review_enabled
        ):
            self._correction_service = AzureOpenAIJapaneseASRCorrectionService(
                api_key=settings.azure_openai_api_key,
                endpoint=settings.azure_openai_endpoint,
                account_name=settings.azure_openai_account_name,
                model=settings.azure_openai_model,
                api_version=settings.azure_openai_api_version,
            )
        else:
            self._correction_service = configured_correction_service

        configured_judge_service = judge_service or NoopJapaneseASRHallucinationJudgeService()
        if (
            isinstance(configured_judge_service, NoopJapaneseASRHallucinationJudgeService)
            and settings.azure_openai_enabled
            and settings.lecture_live_asr_review_enabled
        ):
            judge_model = (
                settings.azure_openai_judge_model.strip()
                or settings.azure_openai_model
            )
            self._judge_service = AzureOpenAIJapaneseASRHallucinationJudgeService(
                api_key=settings.azure_openai_api_key,
                endpoint=settings.azure_openai_endpoint,
                account_name=settings.azure_openai_account_name,
                model=judge_model,
                api_version=settings.azure_openai_api_version,
                timeout_seconds=settings.asr_judge_timeout_seconds,
                obvious_threshold=settings.asr_hallucination_obvious_threshold,
            )
        else:
            self._judge_service = configured_judge_service

        self._subtitle_review_service = subtitle_review_service or SubtitleReviewService(
            correction_service=self._correction_service,
            judge_service=self._judge_service,
            retry_max=settings.asr_audit_retry_max,
        )

    async def start_session(
        self,
        request: LectureSessionStartRequest,
    ) -> LectureSessionStartResponse:
        """Create a new active lecture session."""
        for attempt in range(WRITE_RETRY_ATTEMPTS):
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
            try:
                await self._db.flush()
                return LectureSessionStartResponse(
                    session_id=session.id,
                    status="active",
                )
            except OperationalError as exc:
                if not await self._handle_locked_write_retry(
                    exc=exc,
                    operation_name="start_session.flush",
                    attempt=attempt,
                ):
                    raise
        raise RuntimeError("unreachable")

    async def ingest_speech_chunk(
        self,
        request: SpeechChunkIngestRequest,
    ) -> SpeechChunkIngestResponse:
        """Persist a finalized speech event for an active session."""
        original_text = request.text
        display_text = original_text.strip()

        for attempt in range(WRITE_RETRY_ATTEMPTS):
            await self._get_active_session(request.session_id)

            speech_event = SpeechEvent(
                session_id=request.session_id,
                start_ms=request.start_ms,
                end_ms=request.end_ms,
                original_text=original_text,
                text=display_text,
                confidence=request.confidence,
                is_final=request.is_final,
                speaker=request.speaker,
            )
            self._db.add(speech_event)
            try:
                await self._db.flush()
                return SpeechChunkIngestResponse(
                    event_id=speech_event.id,
                    session_id=request.session_id,
                    accepted=True,
                )
            except OperationalError as exc:
                if not await self._handle_locked_write_retry(
                    exc=exc,
                    operation_name="ingest_speech_chunk.flush",
                    attempt=attempt,
                ):
                    raise
        raise RuntimeError("unreachable")

    async def audit_and_apply_speech_chunk(
        self,
        *,
        session_id: str,
        event_id: str,
    ) -> SpeechChunkAuditApplyResponse:
        """Audit already-displayed subtitle text and update it in-place."""
        for attempt in range(WRITE_RETRY_ATTEMPTS):
            await self._get_active_session(session_id)
            event = await self._get_speech_event(session_id=session_id, event_id=event_id)
            source_text = (event.original_text or event.text).strip()
            if not settings.lecture_live_asr_review_enabled:
                return SpeechChunkAuditApplyResponse(
                    session_id=session_id,
                    event_id=event.id,
                    original_text=event.original_text or source_text,
                    corrected_text=event.text,
                    updated=False,
                    review_status="review_failed",
                    reviewed=False,
                    was_corrected=False,
                    retry_count=0,
                    failure_reason="feature_disabled",
                )
            review_result = await self._subtitle_review_service.review(source_text)
            updated = review_result.was_corrected and review_result.corrected_text != event.text
            event.text = review_result.corrected_text
            if event.original_text is None:
                event.original_text = source_text

            for attempt_row in review_result.attempts:
                self._db.add(
                    SpeechReviewHistory(
                        session_id=session_id,
                        speech_event_id=event.id,
                        attempt_no=attempt_row.attempt_no,
                        review_status=attempt_row.review_status,
                        input_text=attempt_row.input_text,
                        candidate_text=attempt_row.candidate_text,
                        final_text=attempt_row.corrected_text,
                        was_corrected=attempt_row.was_corrected,
                        failure_reason=attempt_row.failure_reason,
                        judge_model=(
                            settings.azure_openai_judge_model.strip()
                            or settings.azure_openai_model
                        )
                        if settings.azure_openai_enabled
                        else "noop",
                        judge_confidence=attempt_row.judge_confidence,
                        completed_at=datetime.now(UTC),
                    )
                )

            try:
                await self._db.flush()
                return SpeechChunkAuditApplyResponse(
                    session_id=session_id,
                    event_id=event.id,
                    original_text=event.original_text or source_text,
                    corrected_text=event.text,
                    updated=updated,
                    review_status=review_result.review_status,
                    reviewed=review_result.review_status == "reviewed",
                    was_corrected=review_result.was_corrected,
                    retry_count=review_result.retry_count,
                    failure_reason=review_result.failure_reason,
                )
            except OperationalError as exc:
                if not await self._handle_locked_write_retry(
                    exc=exc,
                    operation_name="audit_and_apply_speech_chunk.flush",
                    attempt=attempt,
                ):
                    raise
        raise RuntimeError("unreachable")

    async def ingest_visual_event(
        self,
        request: VisualEventIngestRequest,
        image_bytes: bytes,
    ) -> VisualEventIngestResponse:
        """Persist an OCR visual event for an active session."""
        ocr_result = await self._extract_ocr_result(request, image_bytes)
        quality = self._classify_visual_quality(ocr_result.confidence)

        for attempt in range(WRITE_RETRY_ATTEMPTS):
            await self._get_active_session(request.session_id)

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
            try:
                await self._db.flush()
                return VisualEventIngestResponse(
                    event_id=visual_event.id,
                    ocr_text=visual_event.ocr_text,
                    ocr_confidence=visual_event.ocr_confidence,
                    quality=quality,
                )
            except OperationalError as exc:
                if not await self._handle_locked_write_retry(
                    exc=exc,
                    operation_name="ingest_visual_event.flush",
                    attempt=attempt,
                ):
                    raise
        raise RuntimeError("unreachable")

    async def update_lang_mode(
        self,
        session_id: str,
        lang_mode: str,
    ) -> LectureSessionLangModeUpdateResponse:
        """Update language mode for an active session.

        Note: This only updates the session's lang_mode field.
        Existing summaries are NOT regenerated.
        New summaries will use the updated lang_mode.
        """
        for attempt in range(WRITE_RETRY_ATTEMPTS):
            session = await self._get_active_session(session_id)
            session.lang_mode = lang_mode
            try:
                await self._db.flush()
                return LectureSessionLangModeUpdateResponse(
                    session_id=session.id,
                    lang_mode=session.lang_mode,
                    status="active",
                )
            except OperationalError as exc:
                if not await self._handle_locked_write_retry(
                    exc=exc,
                    operation_name="update_lang_mode.flush",
                    attempt=attempt,
                ):
                    raise
        raise RuntimeError("unreachable")

    async def _handle_locked_write_retry(
        self,
        *,
        exc: OperationalError,
        operation_name: str,
        attempt: int,
    ) -> bool:
        if not is_sqlite_locked_error(exc) or attempt >= WRITE_RETRY_ATTEMPTS - 1:
            return False

        await self._db.rollback()
        delay = WRITE_RETRY_BASE_DELAY_SECONDS * (2**attempt)
        logger.warning(
            "SQLite lock detected during %s; retrying in %.3fs (attempt %d/%d)",
            operation_name,
            delay,
            attempt + 1,
            WRITE_RETRY_ATTEMPTS,
        )
        await asyncio.sleep(delay)
        return True

    async def _get_active_session(self, session_id: str) -> LectureSession:
        """Fetch the session scoped to user and ensure it is active."""
        user_id_candidates = get_user_id_candidates(self._user_id)
        session_result = await self._db.execute(
            select(LectureSession).where(
                LectureSession.id == session_id,
                LectureSession.user_id.in_(user_id_candidates),
            )
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            raise LectureSessionNotFoundError(
                f"lecture session not found: {session_id}"
            )

        if session.status not in ACTIVE_SESSION_STATUSES:
            raise LectureSessionInactiveError(
                f"lecture session is not active: {session_id}"
            )
        return session

    async def _get_speech_event(self, *, session_id: str, event_id: str) -> SpeechEvent:
        """Fetch speech event by ID scoped to session ownership."""
        result = await self._db.execute(
            select(SpeechEvent).where(
                SpeechEvent.id == event_id,
                SpeechEvent.session_id == session_id,
            )
        )
        speech_event = result.scalar_one_or_none()
        if speech_event is None:
            raise LectureSpeechEventNotFoundError(
                f"speech event not found: {event_id}"
            )
        return speech_event

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

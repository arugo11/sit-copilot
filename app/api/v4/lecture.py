"""Lecture live API endpoints."""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_lecture_token, require_user_id
from app.core.config import settings
from app.db.session import get_db
from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.summary_window import SummaryWindow
from app.models.visual_event import VisualEvent
from app.schemas.lecture import (
    MAX_VISUAL_IMAGE_BYTES,
    LectureSessionFinalizeRequest,
    LectureSessionFinalizeResponse,
    LectureSessionLangModeUpdateRequest,
    LectureSessionLangModeUpdateResponse,
    LectureSessionStartRequest,
    LectureSessionStartResponse,
    LectureSummaryKeyTerm,
    LectureSummaryLatestResponse,
    LectureVisualSource,
    SpeechChunkAuditApplyRequest,
    SpeechChunkAuditApplyResponse,
    SpeechChunkIngestRequest,
    SpeechChunkIngestResponse,
    SubtitleAuditRequest,
    SubtitleAuditResponse,
    SubtitleTransformRequest,
    SubtitleTransformResponse,
    TranscriptKeyTermsRequest,
    TranscriptKeyTermsResponse,
    VisualEventIngestRequest,
    VisualEventIngestResponse,
)
from app.services.asr_hallucination_judge_service import (
    AzureOpenAIJapaneseASRHallucinationJudgeService,
    JapaneseASRHallucinationJudgeService,
    NoopJapaneseASRHallucinationJudgeService,
)
from app.services.asr_japanese_correction_service import (
    AzureOpenAIJapaneseASRCorrectionService,
    JapaneseASRCorrectionService,
    NoopJapaneseASRCorrectionService,
)
from app.services.asr_subtitle_review_service import SubtitleReviewService
from app.services.azure_search_service import (
    AzureSearchService,
    get_shared_azure_search_service,
)
from app.services.lecture_finalize_service import (
    LectureFinalizeService,
    LectureSessionStateError,
    SqlAlchemyLectureFinalizeService,
)
from app.services.lecture_index_service import (
    AzureLectureIndexService,
    BM25LectureIndexService,
    LectureIndexService,
)
from app.services.lecture_keyterms_service import (
    AzureOpenAILectureKeyTermsService,
    LectureKeyTermsError,
    LectureKeyTermsService,
    UnavailableLectureKeyTermsService,
)
from app.services.lecture_live_service import (
    LectureLiveService,
    LectureSessionInactiveError,
    LectureSessionNotFoundError,
    LectureSpeechEventNotFoundError,
    SqlAlchemyLectureLiveService,
)
from app.services.lecture_retrieval_service import (
    BM25LectureRetrievalService,
    get_shared_lecture_retrieval_service,
)
from app.services.lecture_summary_generator_service import (
    AzureOpenAILectureSummaryGeneratorService,
    LectureSummaryGeneratorService,
    UnavailableLectureSummaryGeneratorService,
)
from app.services.lecture_summary_service import (
    LectureSummaryService,
    SqlAlchemyLectureSummaryService,
)
from app.services.live_caption_transform_service import (
    AzureOpenAILiveCaptionTransformService,
    CaptionTransformService,
)
from app.services.observability import (
    NoopWeaveObserverService,
    WeaveObserverService,
)
from app.services.observed_lecture_finalize_service import (
    ObservedLectureFinalizeService,
)
from app.services.observed_lecture_live_service import ObservedLectureLiveService
from app.services.observed_lecture_summary_generator_service import (
    ObservedLectureSummaryGeneratorService,
)
from app.services.observed_lecture_summary_service import (
    ObservedLectureSummaryService,
)
from app.services.vision_ocr_service import NoopVisionOCRService, VisionOCRService

router = APIRouter(
    prefix="/lecture",
    tags=["lecture"],
    dependencies=[Depends(require_lecture_token)],
)

SSE_POLL_INTERVAL_SECONDS = 1.0
SSE_BATCH_LIMIT = 20
MAX_ASSIST_SUMMARY_POINTS = 3
MAX_ASSIST_TERMS = 4
MAX_OCR_EXCERPT_CHARS = 80
SSE_KEEPALIVE = ": keep-alive\n\n"


@dataclass(slots=True)
class _EventOffsets:
    speech: int = 0
    visual: int = 0
    summary: int = 0


def _is_jpeg_payload(image_bytes: bytes) -> bool:
    """Check JPEG signature bytes."""
    return image_bytes.startswith(b"\xff\xd8\xff")


def _to_sse_payload(event: dict[str, object]) -> str:
    serialized = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"data: {serialized}\n\n"


def _build_thumbnail_data_url(source: str) -> str:
    label = "Slide" if source == "slide" else "Board"
    fill_color = "#e2e8f0" if source == "slide" else "#cbd5e1"
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360'>"
        f"<rect width='100%' height='100%' fill='{fill_color}'/>"
        "<text x='50%' y='50%' text-anchor='middle' dominant-baseline='middle' "
        "font-family='Segoe UI, sans-serif' font-size='28' fill='#0f172a'>"
        f"{label}"
        "</text>"
        "</svg>"
    )
    return f"data:image/svg+xml,{quote(svg)}"


def _ocr_excerpt(text: str, max_chars: int = MAX_OCR_EXCERPT_CHARS) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3]}..."


def _extract_summary_points(summary_text: str) -> list[str]:
    cleaned = " ".join(summary_text.split())
    if not cleaned:
        return []

    candidates = [part.strip() for part in cleaned.replace("?", "。").split("。")]
    points = [part for part in candidates if part]
    return points[:MAX_ASSIST_SUMMARY_POINTS]


def _extract_assist_terms(key_terms_raw: object) -> list[dict[str, str]]:
    if not isinstance(key_terms_raw, list):
        return []

    terms: list[dict[str, str]] = []
    for item in key_terms_raw:
        # Support both legacy string format and new dict format
        if isinstance(item, str):
            term = item.strip()
            if not term:
                continue
            terms.append(
                {
                    "term": term,
                    "explanation": "Generated from lecture summary evidence.",
                    "translation": term,
                }
            )
        elif isinstance(item, dict):
            raw_term = item.get("term", "")  # type: ignore[arg-type]
            if not isinstance(raw_term, str):
                continue
            term = raw_term.strip()
            if not term:
                continue
            explanation = item.get("explanation")  # type: ignore[arg-type]
            translation = item.get("translation")  # type: ignore[arg-type]
            terms.append(
                {
                    "term": term,
                    "explanation": explanation
                    if isinstance(explanation, str)
                    else "Generated from lecture summary evidence.",
                    "translation": translation
                    if isinstance(translation, str)
                    else term,
                }
            )

        if len(terms) >= MAX_ASSIST_TERMS:
            break
    return terms


async def _ensure_stream_session_access(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> None:
    result = await db.execute(
        select(LectureSession.status).where(
            LectureSession.id == session_id,
            LectureSession.user_id == user_id,
        )
    )
    session_status = result.scalar_one_or_none()

    if session_status is None:
        raise LectureSessionNotFoundError(f"lecture session not found: {session_id}")
    if session_status not in {"active", "finalized"}:
        raise LectureSessionInactiveError(
            f"lecture session state does not allow stream: {session_status}"
        )


async def _fetch_stream_batch(
    *,
    db: AsyncSession,
    session_id: str,
    user_id: str,
    offsets: _EventOffsets,
) -> tuple[str, list[SpeechEvent], list[VisualEvent], list[SummaryWindow]]:
    session_result = await db.execute(
        select(LectureSession.status).where(
            LectureSession.id == session_id,
            LectureSession.user_id == user_id,
        )
    )
    session_status = session_result.scalar_one_or_none()
    if session_status is None:
        raise LectureSessionNotFoundError(f"lecture session not found: {session_id}")
    if session_status not in {"active", "finalized"}:
        raise LectureSessionInactiveError(
            f"lecture session state does not allow stream: {session_status}"
        )

    speech_result = await db.execute(
        select(SpeechEvent)
        .where(SpeechEvent.session_id == session_id)
        .order_by(
            SpeechEvent.start_ms,
            SpeechEvent.end_ms,
            SpeechEvent.created_at,
            SpeechEvent.id,
        )
        .offset(offsets.speech)
        .limit(SSE_BATCH_LIMIT)
    )
    speech_events: list[SpeechEvent] = list(speech_result.scalars().all())
    offsets.speech += len(speech_events)

    visual_result = await db.execute(
        select(VisualEvent)
        .where(VisualEvent.session_id == session_id)
        .order_by(
            VisualEvent.timestamp_ms,
            VisualEvent.created_at,
            VisualEvent.id,
        )
        .offset(offsets.visual)
        .limit(SSE_BATCH_LIMIT)
    )
    visual_events: list[VisualEvent] = list(visual_result.scalars().all())
    offsets.visual += len(visual_events)

    summary_result = await db.execute(
        select(SummaryWindow)
        .where(SummaryWindow.session_id == session_id)
        .order_by(
            SummaryWindow.end_ms,
            SummaryWindow.created_at,
            SummaryWindow.id,
        )
        .offset(offsets.summary)
        .limit(SSE_BATCH_LIMIT)
    )
    summary_windows: list[SummaryWindow] = list(summary_result.scalars().all())
    offsets.summary += len(summary_windows)

    return session_status, speech_events, visual_events, summary_windows


async def _stream_lecture_events(
    *,
    db: AsyncSession,
    request: Request,
    session_id: str,
    user_id: str,
    single_batch: bool = False,
) -> AsyncIterator[str]:
    offsets = _EventOffsets()
    yield _to_sse_payload({"type": "session.status", "payload": {"connection": "live"}})

    while True:
        if await request.is_disconnected():
            break

        try:
            await db.rollback()
            (
                session_status,
                speech_events,
                visual_events,
                summary_windows,
            ) = await _fetch_stream_batch(
                db=db,
                session_id=session_id,
                user_id=user_id,
                offsets=offsets,
            )
        except LectureSessionNotFoundError:
            yield _to_sse_payload(
                {
                    "type": "error",
                    "payload": {
                        "message": "Lecture session not found.",
                        "recoverable": False,
                    },
                }
            )
            return
        except LectureSessionInactiveError:
            yield _to_sse_payload(
                {
                    "type": "error",
                    "payload": {
                        "message": "Lecture session is not active.",
                        "recoverable": False,
                    },
                }
            )
            return

        emitted = False

        for event in speech_events:
            transcript_event_type = (
                "transcript.final" if event.is_final else "transcript.partial"
            )
            transcript_payload: dict[str, object] = {
                "id": event.id,
                "tsStartMs": event.start_ms,
                "tsEndMs": event.end_ms,
                "speakerLabel": event.speaker,
                "sourceLangText": event.text,
                "isPartial": not event.is_final,
                "confidence": event.confidence,
                "sourceRefs": {"audioSegmentId": event.id},
            }
            yield _to_sse_payload(
                {"type": transcript_event_type, "payload": transcript_payload}
            )
            emitted = True

        for event in visual_events:
            frame_payload = {
                "id": event.id,
                "source": event.source,
                "timestampMs": event.timestamp_ms,
                "thumbnailUrl": _build_thumbnail_data_url(event.source),
                "ocrExcerpt": _ocr_excerpt(event.ocr_text),
            }
            yield _to_sse_payload({"type": "source.frame", "payload": frame_payload})
            emitted = True

            ocr_payload = {
                "frameId": event.id,
                "source": event.source,
                "timestampMs": event.timestamp_ms,
                "text": event.ocr_text,
            }
            yield _to_sse_payload({"type": "source.ocr", "payload": ocr_payload})
            emitted = True

        for window in summary_windows:
            summary_points = _extract_summary_points(window.summary_text)
            if summary_points:
                yield _to_sse_payload(
                    {
                        "type": "assist.summary",
                        "payload": {
                            "timestampMs": window.end_ms,
                            "points": summary_points,
                        },
                    }
                )
                emitted = True

            assist_terms = _extract_assist_terms(window.key_terms_json)
            if assist_terms:
                yield _to_sse_payload({"type": "assist.term", "payload": assist_terms})
                emitted = True

        if session_status == "finalized":
            yield _to_sse_payload(
                {"type": "session.status", "payload": {"connection": "degraded"}}
            )
            return
        if single_batch:
            return

        if not emitted:
            yield SSE_KEEPALIVE
        await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)


def get_vision_ocr_service() -> VisionOCRService:
    """Dependency provider for OCR adapter."""
    return NoopVisionOCRService()


def get_lecture_retrieval_service() -> BM25LectureRetrievalService:
    """Dependency provider for shared lecture retrieval service."""
    return get_shared_lecture_retrieval_service()


def _azure_search_available() -> bool:
    return (
        settings.azure_search_enabled
        and bool(settings.azure_search_endpoint.strip())
        and bool(settings.azure_search_api_key.strip())
    )


def _azure_openai_summary_available() -> bool:
    return (
        settings.azure_openai_enabled
        and bool(settings.azure_openai_api_key.strip())
        and bool(settings.azure_openai_endpoint.strip())
        and bool(settings.azure_openai_model.strip())
    )


def get_azure_search_service() -> AzureSearchService:
    """Dependency provider for Azure Search service."""
    return get_shared_azure_search_service(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index_name,
    )


def get_japanese_asr_correction_service() -> JapaneseASRCorrectionService:
    """Dependency provider for Japanese ASR minimal correction service."""
    if settings.azure_openai_enabled:
        return AzureOpenAIJapaneseASRCorrectionService(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            account_name=settings.azure_openai_account_name,
            model=settings.azure_openai_model,
            api_version=settings.azure_openai_api_version,
        )
    return NoopJapaneseASRCorrectionService(
        warning_reason=(
            "azure_openai_disabled_request_fallback env=AZURE_OPENAI_ENABLED|AZURE_OPENAI_ENABLE endpoint=/api/v4/lecture/subtitle/audit using=noop_correction"
        )
    )


def get_japanese_asr_hallucination_judge_service() -> JapaneseASRHallucinationJudgeService:
    """Dependency provider for strict hallucination judge."""
    if settings.azure_openai_enabled:
        judge_model = settings.azure_openai_judge_model.strip() or settings.azure_openai_model
        return AzureOpenAIJapaneseASRHallucinationJudgeService(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            account_name=settings.azure_openai_account_name,
            model=judge_model,
            api_version=settings.azure_openai_api_version,
            timeout_seconds=settings.asr_judge_timeout_seconds,
            obvious_threshold=settings.asr_hallucination_obvious_threshold,
        )
    return NoopJapaneseASRHallucinationJudgeService(
        warning_reason=(
            "azure_openai_judge_disabled_request_fallback env=AZURE_OPENAI_ENABLED|AZURE_OPENAI_ENABLE endpoint=/api/v4/lecture/subtitle/audit using=noop_judge"
        )
    )


def get_subtitle_review_service(
    correction_service: Annotated[
        JapaneseASRCorrectionService,
        Depends(get_japanese_asr_correction_service),
    ],
    judge_service: Annotated[
        JapaneseASRHallucinationJudgeService,
        Depends(get_japanese_asr_hallucination_judge_service),
    ],
) -> SubtitleReviewService:
    """Dependency provider for subtitle review flow (generator + judge)."""
    return SubtitleReviewService(
        correction_service=correction_service,
        judge_service=judge_service,
        retry_max=settings.asr_audit_retry_max,
    )


def get_lecture_live_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[str, Depends(require_user_id)],
    vision_ocr_service: Annotated[VisionOCRService, Depends(get_vision_ocr_service)],
    correction_service: Annotated[
        JapaneseASRCorrectionService,
        Depends(get_japanese_asr_correction_service),
    ],
    judge_service: Annotated[
        JapaneseASRHallucinationJudgeService,
        Depends(get_japanese_asr_hallucination_judge_service),
    ],
    subtitle_review_service: Annotated[
        SubtitleReviewService,
        Depends(get_subtitle_review_service),
    ],
    request: Request,
) -> LectureLiveService:
    """Dependency provider for lecture live service with Weave observation."""
    observer: WeaveObserverService = (
        getattr(request.app.state, "weave_observer", None) or NoopWeaveObserverService()
    )

    inner = SqlAlchemyLectureLiveService(
        db=db,
        user_id=user_id,
        vision_ocr_service=vision_ocr_service,
        correction_service=correction_service,
        judge_service=judge_service,
        subtitle_review_service=subtitle_review_service,
    )
    return ObservedLectureLiveService(inner=inner, observer=observer)


def get_lecture_summary_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> LectureSummaryService:
    """Dependency provider for lecture summary service with Weave observation."""
    observer: WeaveObserverService = (
        getattr(request.app.state, "weave_observer", None) or NoopWeaveObserverService()
    )

    # Create observed summary generator
    summary_generator: LectureSummaryGeneratorService
    if _azure_openai_summary_available():
        inner_generator = AzureOpenAILectureSummaryGeneratorService(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            account_name=settings.azure_openai_account_name,
            model=settings.azure_openai_model,
            keyterms_model=settings.azure_openai_keyterms_model,
        )
        summary_generator = ObservedLectureSummaryGeneratorService(
            inner=inner_generator, observer=observer
        )
    else:
        summary_generator = UnavailableLectureSummaryGeneratorService(
            reason="azure openai summary backend is unavailable"
        )

    inner_service = SqlAlchemyLectureSummaryService(
        db=db,
        summary_generator=summary_generator,
    )
    return ObservedLectureSummaryService(inner=inner_service, observer=observer)


def get_lecture_index_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LectureIndexService:
    """Dependency provider for lecture index builder service."""
    if _azure_search_available():
        return AzureLectureIndexService(
            db=db,
            search_service=get_azure_search_service(),
        )

    return BM25LectureIndexService(
        db=db,
        retrieval_service=get_lecture_retrieval_service(),
    )


def get_lecture_finalize_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[str, Depends(require_user_id)],
    summary_service: Annotated[
        LectureSummaryService, Depends(get_lecture_summary_service)
    ],
    index_service: Annotated[LectureIndexService, Depends(get_lecture_index_service)],
    request: Request,
) -> LectureFinalizeService:
    """Dependency provider for lecture finalize service with Weave observation."""
    observer: WeaveObserverService = (
        getattr(request.app.state, "weave_observer", None) or NoopWeaveObserverService()
    )

    inner = SqlAlchemyLectureFinalizeService(
        db=db,
        user_id=user_id,
        summary_service=summary_service,
        index_service=index_service,
    )
    return ObservedLectureFinalizeService(inner=inner, observer=observer)


def get_lecture_keyterms_service() -> LectureKeyTermsService:
    """Dependency provider for lecture key terms service."""
    if _azure_openai_summary_available():
        return AzureOpenAILectureKeyTermsService(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            account_name=settings.azure_openai_account_name,
            model=settings.azure_openai_model,
        )
    else:
        return UnavailableLectureKeyTermsService(
            reason="azure openai key terms backend is unavailable"
        )


def get_caption_transform_service() -> CaptionTransformService:
    """Dependency provider for live subtitle transform service."""
    return AzureOpenAILiveCaptionTransformService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        account_name=settings.azure_openai_account_name,
        model=settings.azure_openai_model,
        api_version=settings.azure_openai_api_version,
    )


@router.post(
    "/session/start",
    status_code=status.HTTP_200_OK,
    response_model=LectureSessionStartResponse,
)
async def start_lecture_session(
    request: LectureSessionStartRequest,
    service: Annotated[LectureLiveService, Depends(get_lecture_live_service)],
) -> LectureSessionStartResponse:
    """Start a new active lecture session."""
    return await service.start_session(request)


@router.patch(
    "/session/lang-mode",
    status_code=status.HTTP_200_OK,
    response_model=LectureSessionLangModeUpdateResponse,
)
async def update_lecture_session_lang_mode(
    request: LectureSessionLangModeUpdateRequest,
    service: Annotated[LectureLiveService, Depends(get_lecture_live_service)],
) -> LectureSessionLangModeUpdateResponse:
    """Update language mode for an active lecture session.

    Note: This only updates the session's lang_mode field.
    Existing summaries are NOT regenerated.
    New summaries will use the updated lang_mode.
    """
    try:
        result = await service.update_lang_mode(
            session_id=request.session_id,
            lang_mode=request.lang_mode,
        )
        return LectureSessionLangModeUpdateResponse(
            session_id=result.session_id,
            lang_mode=request.lang_mode,
            status="active",
        )
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except LectureSessionInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lecture session is not active.",
        ) from exc


@router.post(
    "/speech/chunk",
    status_code=status.HTTP_200_OK,
    response_model=SpeechChunkIngestResponse,
)
async def ingest_speech_chunk(
    request: SpeechChunkIngestRequest,
    service: Annotated[LectureLiveService, Depends(get_lecture_live_service)],
) -> SpeechChunkIngestResponse:
    """Persist a finalized subtitle chunk."""
    try:
        return await service.ingest_speech_chunk(request)
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except LectureSessionInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lecture session is not active.",
        ) from exc


@router.post(
    "/speech/chunk/audit-apply",
    status_code=status.HTTP_200_OK,
    response_model=SpeechChunkAuditApplyResponse,
)
async def audit_and_apply_speech_chunk(
    request: SpeechChunkAuditApplyRequest,
    service: Annotated[LectureLiveService, Depends(get_lecture_live_service)],
) -> SpeechChunkAuditApplyResponse:
    """Audit displayed speech chunk and replace persisted subtitle text."""
    try:
        return await service.audit_and_apply_speech_chunk(
            session_id=request.session_id,
            event_id=request.event_id,
        )
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except LectureSessionInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lecture session is not active.",
        ) from exc
    except LectureSpeechEventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speech event not found.",
        ) from exc


@router.post(
    "/subtitle/transform",
    status_code=status.HTTP_200_OK,
    response_model=SubtitleTransformResponse,
)
async def transform_subtitle_for_display(
    request: SubtitleTransformRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    transform_service: Annotated[
        CaptionTransformService,
        Depends(get_caption_transform_service),
    ],
) -> SubtitleTransformResponse:
    """Transform subtitle text for selected live subtitle language."""
    await _ensure_stream_session_access(
        db=db,
        session_id=request.session_id,
        user_id=user_id,
    )
    transformed_text = await transform_service.transform(
        text=request.text,
        target_lang_mode=request.target_lang_mode,
    )
    return SubtitleTransformResponse(
        session_id=request.session_id,
        target_lang_mode=request.target_lang_mode,
        transformed_text=transformed_text,
    )


@router.post(
    "/subtitle/audit",
    status_code=status.HTTP_200_OK,
    response_model=SubtitleAuditResponse,
)
async def audit_subtitle_text(
    request: SubtitleAuditRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    review_service: Annotated[
        SubtitleReviewService,
        Depends(get_subtitle_review_service),
    ],
) -> SubtitleAuditResponse:
    """Run immediate subtitle audit/correction for displayed text."""
    await _ensure_stream_session_access(
        db=db,
        session_id=request.session_id,
        user_id=user_id,
    )
    review_result = await review_service.review(request.text)
    return SubtitleAuditResponse(
        session_id=request.session_id,
        original_text=request.text,
        corrected_text=review_result.corrected_text,
        review_status=review_result.review_status,
        reviewed=review_result.review_status == "reviewed",
        was_corrected=review_result.was_corrected,
        retry_count=review_result.retry_count,
        failure_reason=review_result.failure_reason,
    )


@router.post(
    "/visual/event",
    status_code=status.HTTP_200_OK,
    response_model=VisualEventIngestResponse,
)
async def ingest_visual_event(
    session_id: Annotated[str, Form(...)],
    timestamp_ms: Annotated[int, Form(...)],
    source: Annotated[LectureVisualSource, Form(...)],
    change_score: Annotated[float, Form(...)],
    image: Annotated[UploadFile, File(...)],
    service: Annotated[LectureLiveService, Depends(get_lecture_live_service)],
) -> VisualEventIngestResponse:
    """Persist an OCR visual event."""
    max_image_bytes = min(
        settings.lecture_visual_max_image_bytes,
        MAX_VISUAL_IMAGE_BYTES,
    )
    image_bytes = await image.read(max_image_bytes + 1)
    image_content_type = image.content_type or ""

    try:
        request = VisualEventIngestRequest.model_validate(
            {
                "session_id": session_id,
                "timestamp_ms": timestamp_ms,
                "source": source,
                "change_score": change_score,
                "image_content_type": image_content_type,
                "image_size": len(image_bytes),
                "upload_size_limit": max_image_bytes,
                "image_has_jpeg_magic": _is_jpeg_payload(image_bytes),
            }
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    try:
        return await service.ingest_visual_event(request, image_bytes)
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except LectureSessionInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lecture session is not active.",
        ) from exc


@router.get(
    "/events/stream",
    status_code=status.HTTP_200_OK,
)
async def stream_lecture_events(
    request: Request,
    session_id: Annotated[
        str,
        Query(..., min_length=1, max_length=64),
    ],
    user_id: Annotated[str, Depends(require_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    once: Annotated[bool, Query()] = False,
) -> StreamingResponse:
    """Stream lecture events as Server-Sent Events."""
    normalized_session_id = session_id.strip()
    if not normalized_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must not be blank.",
        )

    try:
        await _ensure_stream_session_access(
            db=db,
            session_id=normalized_session_id,
            user_id=user_id,
        )
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except LectureSessionInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lecture session is not active.",
        ) from exc

    return StreamingResponse(
        _stream_lecture_events(
            db=db,
            request=request,
            session_id=normalized_session_id,
            user_id=user_id,
            single_batch=once,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/summary/latest",
    status_code=status.HTTP_200_OK,
    response_model=LectureSummaryLatestResponse,
)
async def get_latest_summary(
    session_id: Annotated[
        str,
        Query(..., min_length=1, max_length=64),
    ],
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[LectureSummaryService, Depends(get_lecture_summary_service)],
) -> LectureSummaryLatestResponse:
    """Return latest 30-second summary for the lecture session."""
    normalized_session_id = session_id.strip()
    if not normalized_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must not be blank.",
        )

    try:
        return await service.get_latest_summary(
            session_id=normalized_session_id,
            user_id=user_id,
        )
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except LectureSessionInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lecture session is not active.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lecture summary backend is unavailable.",
        ) from exc


@router.post(
    "/session/finalize",
    status_code=status.HTTP_200_OK,
    response_model=LectureSessionFinalizeResponse,
)
async def finalize_lecture_session(
    request: LectureSessionFinalizeRequest,
    service: Annotated[
        LectureFinalizeService,
        Depends(get_lecture_finalize_service),
    ],
) -> LectureSessionFinalizeResponse:
    """Finalize a lecture session and generate summary/chunk artifacts."""
    try:
        return await service.finalize(
            session_id=request.session_id,
            build_qa_index=request.build_qa_index,
        )
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except LectureSessionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lecture session state is invalid.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lecture summary backend is unavailable.",
        ) from exc


@router.post(
    "/transcript/analyze-keyterms",
    status_code=status.HTTP_200_OK,
    response_model=TranscriptKeyTermsResponse,
)
async def analyze_transcript_keyterms(
    request: TranscriptKeyTermsRequest,
    service: Annotated[LectureKeyTermsService, Depends(get_lecture_keyterms_service)],
    user_id: Annotated[str, Depends(require_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TranscriptKeyTermsResponse:
    """Analyze transcript for key terms and generate explanations."""
    # Verify session exists and belongs to user
    result = await db.execute(
        select(LectureSession).where(
            LectureSession.id == request.session_id,
            LectureSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        )

    try:
        keyterms_result = await service.extract_key_terms(
            transcript_text=request.transcript_text,
            lang_mode=request.lang_mode,
        )

        # Convert dict result to LectureSummaryKeyTerm objects
        key_terms = [
            LectureSummaryKeyTerm(
                term=term["term"],
                explanation=term.get("explanation", ""),
                translation=term.get("translation", ""),
                evidence_tags=["speech"],
            )
            for term in keyterms_result.key_terms
        ]

        return TranscriptKeyTermsResponse(
            key_terms=key_terms,
            detected_terms=keyterms_result.detected_terms,
        )
    except LectureKeyTermsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Key terms extraction service is unavailable.",
        ) from exc

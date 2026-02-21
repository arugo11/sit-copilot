"""Lecture live API endpoints."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_lecture_token, require_user_id
from app.core.config import settings
from app.db.session import get_db
from app.schemas.lecture import (
    MAX_VISUAL_IMAGE_BYTES,
    LectureSessionFinalizeRequest,
    LectureSessionFinalizeResponse,
    LectureSessionStartRequest,
    LectureSessionStartResponse,
    LectureSummaryLatestResponse,
    LectureVisualSource,
    SpeechChunkIngestRequest,
    SpeechChunkIngestResponse,
    VisualEventIngestRequest,
    VisualEventIngestResponse,
)
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
from app.services.lecture_live_service import (
    LectureLiveService,
    LectureSessionInactiveError,
    LectureSessionNotFoundError,
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
from app.services.vision_ocr_service import NoopVisionOCRService, VisionOCRService

router = APIRouter(
    prefix="/lecture",
    tags=["lecture"],
    dependencies=[Depends(require_lecture_token)],
)


def _is_jpeg_payload(image_bytes: bytes) -> bool:
    """Check JPEG signature bytes."""
    return image_bytes.startswith(b"\xff\xd8\xff")


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


def get_lecture_live_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[str, Depends(require_user_id)],
    vision_ocr_service: Annotated[VisionOCRService, Depends(get_vision_ocr_service)],
) -> LectureLiveService:
    """Dependency provider for lecture live service."""
    return SqlAlchemyLectureLiveService(
        db=db,
        user_id=user_id,
        vision_ocr_service=vision_ocr_service,
    )


def get_lecture_summary_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LectureSummaryService:
    """Dependency provider for lecture summary service."""
    summary_generator: LectureSummaryGeneratorService
    if _azure_openai_summary_available():
        summary_generator = AzureOpenAILectureSummaryGeneratorService(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            model=settings.azure_openai_model,
        )
    else:
        summary_generator = UnavailableLectureSummaryGeneratorService(
            reason="azure openai summary backend is unavailable"
        )
    return SqlAlchemyLectureSummaryService(
        db=db,
        summary_generator=summary_generator,
    )


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
) -> LectureFinalizeService:
    """Dependency provider for lecture finalize service."""
    return SqlAlchemyLectureFinalizeService(
        db=db,
        user_id=user_id,
        summary_service=summary_service,
        index_service=index_service,
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

"""Lecture QA API endpoints."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_lecture_token, require_user_id
from app.core.config import settings
from app.db.session import get_db
from app.schemas.lecture_qa import (
    LectureAskRequest,
    LectureAskResponse,
    LectureAutoTitleDebugLogRequest,
    LectureAutoTitleDebugLogResponse,
    LectureFollowupRequest,
    LectureFollowupResponse,
    LectureIndexBuildRequest,
    LectureIndexBuildResponse,
)
from app.services.azure_search_service import (
    AzureSearchService,
    get_shared_azure_search_service,
)
from app.services.lecture_answerer_service import (
    AzureOpenAILectureAnswererService,
    LectureAnswererService,
)
from app.services.lecture_followup_service import (
    LectureFollowupService,
    SqlAlchemyLectureFollowupService,
)
from app.services.lecture_index_service import (
    AzureLectureIndexService,
    BM25LectureIndexService,
    LectureIndexService,
)
from app.services.lecture_live_service import LectureSessionNotFoundError
from app.services.lecture_qa_service import (
    LectureQAService,
    SqlAlchemyLectureQAService,
)
from app.services.lecture_retrieval_service import (
    AzureSearchLectureRetrievalService,
    LectureRetrievalService,
    get_shared_lecture_retrieval_service,
)
from app.services.lecture_verifier_service import (
    AzureOpenAILectureVerifierService,
    LectureVerifierService,
)
from app.services.observability.weave_observer_service import (
    NoopWeaveObserverService,
    WeaveObserverService,
)
from app.services.observed_lecture_answerer_service import (
    ObservedLectureAnswererService,
)
from app.services.observed_lecture_qa_service import ObservedLectureQAService

router = APIRouter(
    prefix="/lecture/qa",
    tags=["lecture-qa"],
    dependencies=[Depends(require_lecture_token)],
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AUTO_TITLE_DEBUG_LOG_DIR = PROJECT_ROOT / ".log"
AUTO_TITLE_DEBUG_LOG_PATH = AUTO_TITLE_DEBUG_LOG_DIR / "auto-title-debug.log"
AUTO_TITLE_DEBUG_LOG_RELATIVE_PATH = ".log/auto-title-debug.log"
_shared_lecture_answerer_service: AzureOpenAILectureAnswererService | None = None
_shared_lecture_answerer_service_key: (
    tuple[str, str, str, str, int, float, float, str] | None
) = None
QA_DISABLED_ANSWER = "この環境では講義 QA は無効です。"
QA_DISABLED_ACTION_NEXT = "管理者が QA を有効化するまでお待ちください。"


def _append_auto_title_debug_log(
    *,
    user_id: str,
    request: LectureAutoTitleDebugLogRequest,
) -> None:
    AUTO_TITLE_DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "session_id": request.session_id,
        "event": request.event,
        "level": request.level,
        "locale": request.locale,
        "payload": request.payload,
    }
    with AUTO_TITLE_DEBUG_LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        fp.write("\n")


def _azure_search_available() -> bool:
    return (
        settings.azure_search_enabled
        and bool(settings.azure_search_endpoint.strip())
        and bool(settings.azure_search_api_key.strip())
    )


def _lecture_qa_available() -> bool:
    return settings.azure_openai_enabled and settings.lecture_qa_enabled


def _build_qa_disabled_response() -> LectureAskResponse:
    return LectureAskResponse(
        answer=QA_DISABLED_ANSWER,
        confidence="low",
        sources=[],
        verification_summary="feature_disabled",
        action_next=QA_DISABLED_ACTION_NEXT,
        fallback="feature_disabled",
    )


def _build_followup_disabled_response(question: str) -> LectureFollowupResponse:
    return LectureFollowupResponse(
        answer=QA_DISABLED_ANSWER,
        confidence="low",
        sources=[],
        verification_summary="feature_disabled",
        action_next=QA_DISABLED_ACTION_NEXT,
        fallback="feature_disabled",
        resolved_query=question,
    )


def get_weave_observer(request: Request) -> WeaveObserverService:
    """Get Weave observer from app state.

    Args:
        request: FastAPI request object

    Returns:
        WeaveObserverService instance from app state
    """
    return (
        getattr(request.app.state, "weave_observer", None) or NoopWeaveObserverService()
    )


def get_azure_search_service() -> AzureSearchService:
    """Dependency provider for Azure Search service."""
    return get_shared_azure_search_service(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index_name,
    )


def get_lecture_retrieval_service() -> LectureRetrievalService:
    """Dependency provider for lecture retrieval service."""
    if _azure_search_available():
        return AzureSearchLectureRetrievalService(
            search_service=get_azure_search_service(),
        )
    return get_shared_lecture_retrieval_service()


def _lecture_answerer_config_key() -> tuple[str, str, str, str, int, float, float, str]:
    return (
        settings.azure_openai_api_key,
        settings.azure_openai_endpoint,
        settings.azure_openai_account_name,
        settings.azure_openai_model,
        settings.lecture_qa_answer_max_retries,
        settings.lecture_qa_answer_retry_delay_seconds,
        settings.lecture_qa_answer_min_request_interval_seconds,
        settings.azure_openai_api_version,
    )


def get_shared_lecture_answerer_service() -> AzureOpenAILectureAnswererService:
    """Return process-shared answerer service for retry/rate-limit state reuse."""
    global _shared_lecture_answerer_service
    global _shared_lecture_answerer_service_key

    config_key = _lecture_answerer_config_key()
    if (
        _shared_lecture_answerer_service is None
        or _shared_lecture_answerer_service_key != config_key
    ):
        _shared_lecture_answerer_service = AzureOpenAILectureAnswererService(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            account_name=settings.azure_openai_account_name,
            model=settings.azure_openai_model,
            max_retries=settings.lecture_qa_answer_max_retries,
            retry_delay_seconds=settings.lecture_qa_answer_retry_delay_seconds,
            min_request_interval_seconds=settings.lecture_qa_answer_min_request_interval_seconds,
            api_version=settings.azure_openai_api_version,
        )
        _shared_lecture_answerer_service_key = config_key

    return _shared_lecture_answerer_service


def get_lecture_answerer_service(
    observer: Annotated[WeaveObserverService, Depends(get_weave_observer)],
) -> LectureAnswererService:
    """Dependency provider for lecture answerer service.

    Wraps with observed service when Weave is enabled.
    """
    inner_service = get_shared_lecture_answerer_service()

    # Wrap with observed service if Weave is enabled
    if settings.weave.enabled:
        return ObservedLectureAnswererService(
            inner=inner_service,
            observer=observer,
            model=settings.azure_openai_model,
        )

    return inner_service


def get_lecture_verifier_service() -> LectureVerifierService:
    """Dependency provider for lecture verifier service."""
    return AzureOpenAILectureVerifierService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        account_name=settings.azure_openai_account_name,
        model=settings.azure_openai_model,
        api_version=settings.azure_openai_api_version,
    )


def get_lecture_followup_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LectureFollowupService:
    """Dependency provider for lecture follow-up service."""
    return SqlAlchemyLectureFollowupService(
        db=db,
        openai_api_key=settings.azure_openai_api_key,
        openai_endpoint=settings.azure_openai_endpoint,
        openai_account_name=settings.azure_openai_account_name,
        model=settings.azure_openai_model,
        api_version=settings.azure_openai_api_version,
    )


def get_lecture_index_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LectureIndexService:
    """Dependency provider for lecture index service."""
    if _azure_search_available():
        return AzureLectureIndexService(
            db=db,
            search_service=get_azure_search_service(),
        )

    return BM25LectureIndexService(
        db=db,
        retrieval_service=get_shared_lecture_retrieval_service(),
    )


def get_lecture_qa_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    retriever: Annotated[
        LectureRetrievalService, Depends(get_lecture_retrieval_service)
    ],
    answerer: Annotated[LectureAnswererService, Depends(get_lecture_answerer_service)],
    verifier: Annotated[LectureVerifierService, Depends(get_lecture_verifier_service)],
    followup: Annotated[LectureFollowupService, Depends(get_lecture_followup_service)],
    observer: Annotated[WeaveObserverService, Depends(get_weave_observer)],
) -> LectureQAService:
    """Dependency provider for lecture QA orchestration service.

    Wraps with observed service when Weave is enabled.
    """
    inner_service = SqlAlchemyLectureQAService(
        db=db,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
        retrieval_limit=settings.lecture_qa_retrieval_limit,
        citation_limit=settings.lecture_qa_citation_limit,
    )

    # Wrap with observed service if Weave is enabled
    if settings.weave.enabled:
        return ObservedLectureQAService(inner=inner_service, observer=observer)

    return inner_service


@router.post(
    "/index/build",
    status_code=status.HTTP_200_OK,
    response_model=LectureIndexBuildResponse,
)
async def build_qa_index(
    request: LectureIndexBuildRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[LectureIndexService, Depends(get_lecture_index_service)],
) -> LectureIndexBuildResponse:
    """Build lecture QA index for the session (Azure or BM25 backend)."""
    try:
        return await service.build_index(
            session_id=request.session_id,
            user_id=user_id,
            rebuild=request.rebuild,
        )
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lecture index backend is unavailable.",
        ) from exc


@router.post(
    "/ask",
    status_code=status.HTTP_200_OK,
    response_model=LectureAskResponse,
)
async def ask_question(
    request: LectureAskRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[LectureQAService, Depends(get_lecture_qa_service)],
) -> LectureAskResponse:
    """Answer a lecture question using configured retrieval + Azure OpenAI."""
    if not _lecture_qa_available():
        return _build_qa_disabled_response()

    try:
        return await service.ask(
            session_id=request.session_id,
            user_id=user_id,
            question=request.question,
            lang_mode=request.lang_mode,
            retrieval_mode=request.retrieval_mode,
            top_k=request.top_k,
            context_window=request.context_window,
        )
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lecture QA backend is unavailable.",
        ) from exc


@router.post(
    "/autotitle/log",
    status_code=status.HTTP_200_OK,
    response_model=LectureAutoTitleDebugLogResponse,
)
async def log_autotitle_debug(
    request: LectureAutoTitleDebugLogRequest,
    user_id: Annotated[str, Depends(require_user_id)],
) -> LectureAutoTitleDebugLogResponse:
    """Append auto-title debug event to local JSONL log file."""
    try:
        _append_auto_title_debug_log(user_id=user_id, request=request)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write auto-title debug log.",
        ) from exc

    return LectureAutoTitleDebugLogResponse(
        status="logged",
        log_file=AUTO_TITLE_DEBUG_LOG_RELATIVE_PATH,
    )


@router.post(
    "/followup",
    status_code=status.HTTP_200_OK,
    response_model=LectureFollowupResponse,
)
async def ask_followup(
    request: LectureFollowupRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[LectureQAService, Depends(get_lecture_qa_service)],
) -> LectureFollowupResponse:
    """Answer a follow-up question with conversation context."""
    if not _lecture_qa_available():
        return _build_followup_disabled_response(request.question)

    try:
        return await service.followup(
            session_id=request.session_id,
            user_id=user_id,
            question=request.question,
            lang_mode=request.lang_mode,
            retrieval_mode=request.retrieval_mode,
            top_k=request.top_k,
            context_window=request.context_window,
            history_turns=request.history_turns,
        )
    except LectureSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture session not found.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lecture QA backend is unavailable.",
        ) from exc

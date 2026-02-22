"""Lecture QA API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_lecture_token, require_user_id
from app.core.config import settings
from app.db.session import get_db
from app.schemas.lecture_qa import (
    LectureAskRequest,
    LectureAskResponse,
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
from app.services.observability.weave_observer_service import WeaveObserverService
from app.services.observed_lecture_answerer_service import (
    ObservedLectureAnswererService,
)
from app.services.observed_lecture_qa_service import ObservedLectureQAService

router = APIRouter(
    prefix="/lecture/qa",
    tags=["lecture-qa"],
    dependencies=[Depends(require_lecture_token)],
)


def _azure_search_available() -> bool:
    return (
        settings.azure_search_enabled
        and bool(settings.azure_search_endpoint.strip())
        and bool(settings.azure_search_api_key.strip())
    )


def get_weave_observer(request: Request) -> WeaveObserverService:
    """Get Weave observer from app state.

    Args:
        request: FastAPI request object

    Returns:
        WeaveObserverService instance from app state
    """
    return request.app.state.weave_observer


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


def get_lecture_answerer_service(
    observer: Annotated[WeaveObserverService, Depends(get_weave_observer)],
) -> LectureAnswererService:
    """Dependency provider for lecture answerer service.

    Wraps with observed service when Weave is enabled.
    """
    inner_service = AzureOpenAILectureAnswererService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        account_name=settings.azure_openai_account_name,
        model=settings.azure_openai_model,
        api_version=settings.azure_openai_api_version,
    )

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

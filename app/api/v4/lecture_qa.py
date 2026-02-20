"""Lecture QA API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
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
from app.services.lecture_answerer_service import (
    AzureOpenAILectureAnswererService,
    LectureAnswererService,
)
from app.services.lecture_followup_service import (
    LectureFollowupService,
    SqlAlchemyLectureFollowupService,
)
from app.services.lecture_index_service import (
    BM25LectureIndexService,
    LectureIndexService,
)
from app.services.lecture_qa_service import (
    LectureQAService,
    SqlAlchemyLectureQAService,
)
from app.services.lecture_retrieval_service import (
    BM25LectureRetrievalService,
    LectureRetrievalService,
)
from app.services.lecture_verifier_service import (
    AzureOpenAILectureVerifierService,
    LectureVerifierService,
)

router = APIRouter(
    prefix="/lecture/qa",
    tags=["lecture-qa"],
    dependencies=[Depends(require_lecture_token)],
)

_shared_lecture_retrieval_service = BM25LectureRetrievalService()


def get_lecture_retrieval_service() -> BM25LectureRetrievalService:
    """Dependency provider for lecture retrieval service."""
    return _shared_lecture_retrieval_service


def get_lecture_answerer_service() -> LectureAnswererService:
    """Dependency provider for lecture answerer service."""
    return AzureOpenAILectureAnswererService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        model=settings.azure_openai_model,
    )


def get_lecture_verifier_service() -> LectureVerifierService:
    """Dependency provider for lecture verifier service."""
    return AzureOpenAILectureVerifierService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        model=settings.azure_openai_model,
    )


def get_lecture_followup_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LectureFollowupService:
    """Dependency provider for lecture follow-up service."""
    return SqlAlchemyLectureFollowupService(
        db=db,
        openai_api_key=settings.azure_openai_api_key,
        openai_endpoint=settings.azure_openai_endpoint,
        model=settings.azure_openai_model,
    )


def get_lecture_index_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    retriever: Annotated[
        BM25LectureRetrievalService, Depends(get_lecture_retrieval_service)
    ],
) -> LectureIndexService:
    """Dependency provider for lecture index service."""
    return BM25LectureIndexService(
        db=db,
        retrieval_service=retriever,
    )


def get_lecture_qa_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    retriever: Annotated[
        LectureRetrievalService, Depends(get_lecture_retrieval_service)
    ],
    answerer: Annotated[LectureAnswererService, Depends(get_lecture_answerer_service)],
    verifier: Annotated[LectureVerifierService, Depends(get_lecture_verifier_service)],
    followup: Annotated[LectureFollowupService, Depends(get_lecture_followup_service)],
) -> LectureQAService:
    """Dependency provider for lecture QA orchestration service."""
    return SqlAlchemyLectureQAService(
        db=db,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
        retrieval_limit=settings.lecture_qa_retrieval_limit,
    )


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
    """Build BM25 search index from finalized speech events."""
    return await service.build_index(
        session_id=request.session_id,
        user_id=user_id,
        rebuild=request.rebuild,
    )


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
    """Answer a lecture question using BM25 retrieval + Azure OpenAI."""
    return await service.ask(
        session_id=request.session_id,
        user_id=user_id,
        question=request.question,
        lang_mode=request.lang_mode,
        retrieval_mode=request.retrieval_mode,
        top_k=request.top_k,
        context_window=request.context_window,
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

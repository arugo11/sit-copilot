"""Procedure QA API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthContext,
    require_procedure_token,
    resolve_auth_context,
    resolve_rate_limit_user_id,
)
from app.core.config import settings
from app.core.rate_limit import (
    RateLimitPolicy,
    SlidingWindowRateLimiter,
    enforce_rate_limit,
)
from app.db.session import get_db
from app.schemas.procedure import ProcedureAskRequest, ProcedureAskResponse
from app.services.procedure_answerer_service import (
    AzureOpenAIProcedureAnswererService,
    ProcedureAnswererService,
)
from app.services.procedure_qa_service import (
    ProcedureQAService,
    SqlAlchemyProcedureQAService,
)
from app.services.procedure_retrieval_service import (
    AzureProcedureSearchService,
    AzureSearchProcedureRetrievalService,
    NoopProcedureRetrievalService,
    ProcedureRetrievalService,
    ProcedureSearchService,
)
from app.services.lecture_verifier_service import (
    AzureOpenAILectureVerifierService,
    LectureVerifierService,
)

router = APIRouter(
    prefix="/procedure",
    tags=["procedure"],
    dependencies=[Depends(require_procedure_token)],
)
_procedure_rate_limiter = SlidingWindowRateLimiter()


def _azure_search_available() -> bool:
    return (
        settings.azure_search_enabled
        and bool(settings.azure_search_endpoint.strip())
        and bool(settings.azure_search_api_key.strip())
    )


def get_procedure_search_service() -> ProcedureSearchService:
    """Dependency provider for procedure search service."""
    return AzureProcedureSearchService(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.procedure_search_index_name,
    )


def get_procedure_retrieval_service() -> ProcedureRetrievalService:
    """Dependency provider for procedure retrieval service."""
    if _azure_search_available():
        return AzureSearchProcedureRetrievalService(
            search_service=get_procedure_search_service(),
        )
    return NoopProcedureRetrievalService()


def get_procedure_answerer_service() -> ProcedureAnswererService:
    """Dependency provider for procedure answerer service."""
    return AzureOpenAIProcedureAnswererService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        account_name=settings.azure_openai_account_name,
        model=settings.azure_openai_model,
        api_version=settings.azure_openai_api_version,
    )


def get_procedure_verifier_service() -> LectureVerifierService:
    """Dependency provider for procedure verifier service."""
    return AzureOpenAILectureVerifierService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        account_name=settings.azure_openai_account_name,
        model=settings.azure_openai_model,
        api_version=settings.azure_openai_api_version,
    )


def get_procedure_qa_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    retriever: Annotated[
        ProcedureRetrievalService, Depends(get_procedure_retrieval_service)
    ],
    answerer: Annotated[
        ProcedureAnswererService, Depends(get_procedure_answerer_service)
    ],
    verifier: Annotated[
        LectureVerifierService, Depends(get_procedure_verifier_service)
    ],
) -> ProcedureQAService:
    """Dependency provider for procedure QA orchestration service."""
    return SqlAlchemyProcedureQAService(
        db=db,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        retrieval_limit=settings.procedure_retrieval_limit,
        no_source_fallback=settings.procedure_no_source_fallback,
        no_source_action_next=settings.procedure_no_source_action_next,
        backend_failure_fallback=settings.procedure_backend_failure_fallback,
    )


@router.post(
    "/ask",
    status_code=status.HTTP_200_OK,
    response_model=ProcedureAskResponse,
)
async def ask_procedure(
    http_request: Request,
    request: ProcedureAskRequest,
    auth: Annotated[AuthContext, Depends(resolve_auth_context)],
    service: Annotated[ProcedureQAService, Depends(get_procedure_qa_service)],
) -> ProcedureAskResponse:
    """Answer procedure question using evidence-first policy."""
    await enforce_rate_limit(
        http_request,
        limiter=_procedure_rate_limiter,
        policy=RateLimitPolicy(
            bucket="procedure-ask",
            max_requests=settings.public_demo_rate_limit_procedure_per_minute,
        ),
        user_id=resolve_rate_limit_user_id(http_request, auth),
    )
    return await service.ask(request)

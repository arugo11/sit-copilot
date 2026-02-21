"""Procedure QA API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_procedure_token
from app.core.config import settings
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

router = APIRouter(
    prefix="/procedure",
    tags=["procedure"],
    dependencies=[Depends(require_procedure_token)],
)


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
    )


def get_procedure_qa_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    retriever: Annotated[
        ProcedureRetrievalService, Depends(get_procedure_retrieval_service)
    ],
    answerer: Annotated[
        ProcedureAnswererService, Depends(get_procedure_answerer_service)
    ],
) -> ProcedureQAService:
    """Dependency provider for procedure QA orchestration service."""
    return SqlAlchemyProcedureQAService(
        db=db,
        retriever=retriever,
        answerer=answerer,
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
    request: ProcedureAskRequest,
    service: Annotated[ProcedureQAService, Depends(get_procedure_qa_service)],
) -> ProcedureAskResponse:
    """Answer procedure question using evidence-first policy."""
    return await service.ask(request)

"""Procedure QA API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_procedure_token
from app.core.config import settings
from app.db.session import get_db
from app.schemas.procedure import ProcedureAskRequest, ProcedureAskResponse
from app.services.procedure_answerer_service import (
    FakeProcedureAnswererService,
    ProcedureAnswererService,
)
from app.services.procedure_qa_service import (
    ProcedureQAService,
    SqlAlchemyProcedureQAService,
)
from app.services.procedure_retrieval_service import (
    FakeProcedureRetrievalService,
    ProcedureRetrievalService,
)

router = APIRouter(
    prefix="/procedure",
    tags=["procedure"],
    dependencies=[Depends(require_procedure_token)],
)


def get_procedure_retrieval_service() -> ProcedureRetrievalService:
    """Dependency provider for procedure retrieval service."""
    return FakeProcedureRetrievalService()


def get_procedure_answerer_service() -> ProcedureAnswererService:
    """Dependency provider for procedure answerer service."""
    return FakeProcedureAnswererService()


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

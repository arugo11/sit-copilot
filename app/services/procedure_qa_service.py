"""Procedure QA orchestration service."""

from time import perf_counter
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa_turn import QATurn
from app.schemas.procedure import (
    ProcedureAskRequest,
    ProcedureAskResponse,
    ProcedureSource,
)
from app.services.procedure_answerer_service import (
    ProcedureAnswerDraft,
    ProcedureAnswererService,
)
from app.services.procedure_retrieval_service import ProcedureRetrievalService

__all__ = ["ProcedureQAService", "SqlAlchemyProcedureQAService"]

PROCEDURE_QA_FEATURE = "procedure_qa"
DEFAULT_RETRIEVAL_LIMIT = 3
DEFAULT_NO_SOURCE_FALLBACK = "現在の質問に対応する公式根拠が見つかりませんでした。"
DEFAULT_NO_SOURCE_ACTION_NEXT = (
    "教務課または公式ポータルで最新の手続き情報を確認してください。"
)


class ProcedureQAService(Protocol):
    """Interface for procedure QA orchestration."""

    async def ask(self, request: ProcedureAskRequest) -> ProcedureAskResponse:
        """Answer a procedure question with evidence-first policy."""
        ...


class SqlAlchemyProcedureQAService:
    """Procedure QA service with rootless-answer guard and persistence."""

    def __init__(
        self,
        db: AsyncSession,
        retriever: ProcedureRetrievalService,
        answerer: ProcedureAnswererService,
        retrieval_limit: int = DEFAULT_RETRIEVAL_LIMIT,
        no_source_fallback: str = DEFAULT_NO_SOURCE_FALLBACK,
        no_source_action_next: str = DEFAULT_NO_SOURCE_ACTION_NEXT,
    ) -> None:
        self._db = db
        self._retriever = retriever
        self._answerer = answerer
        self._retrieval_limit = max(1, retrieval_limit)
        self._no_source_fallback = no_source_fallback
        self._no_source_action_next = no_source_action_next

    async def ask(self, request: ProcedureAskRequest) -> ProcedureAskResponse:
        """Execute retrieval + answer generation and persist qa turn."""
        started_at = perf_counter()
        sources = await self._retriever.retrieve(
            query=request.query,
            lang_mode=request.lang_mode,
            limit=self._retrieval_limit,
        )

        if not sources:
            response = ProcedureAskResponse(
                answer=self._no_source_fallback,
                confidence="low",
                sources=[],
                action_next=self._no_source_action_next,
                fallback=self._no_source_fallback,
            )
            await self._persist_turn(
                question=request.query,
                response=response,
                latency_ms=self._to_latency_ms(started_at),
            )
            return response

        draft = await self._answerer.answer(
            query=request.query,
            lang_mode=request.lang_mode,
            sources=sources,
        )
        response = self._build_success_response(
            draft=draft,
            sources=sources,
        )
        await self._persist_turn(
            question=request.query,
            response=response,
            latency_ms=self._to_latency_ms(started_at),
        )
        return response

    def _build_success_response(
        self, draft: ProcedureAnswerDraft, sources: list[ProcedureSource]
    ) -> ProcedureAskResponse:
        return ProcedureAskResponse(
            answer=draft.answer,
            confidence=draft.confidence,
            sources=sources,
            action_next=draft.action_next,
            fallback="",
        )

    async def _persist_turn(
        self,
        *,
        question: str,
        response: ProcedureAskResponse,
        latency_ms: int,
    ) -> None:
        citations = [source.model_dump() for source in response.sources]
        source_ids = [source.source_id for source in response.sources]

        qa_turn = QATurn(
            session_id=None,
            feature=PROCEDURE_QA_FEATURE,
            question=question,
            answer=response.answer,
            confidence=response.confidence,
            citations_json=citations,
            retrieved_chunk_ids_json=source_ids,
            latency_ms=latency_ms,
            verifier_supported=False,
        )
        self._db.add(qa_turn)
        await self._db.flush()

    @staticmethod
    def _to_latency_ms(started_at: float) -> int:
        elapsed = perf_counter() - started_at
        return max(0, int(elapsed * 1000))

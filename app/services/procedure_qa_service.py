"""Procedure QA orchestration service."""

from time import perf_counter
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa_turn import QATurn
from app.schemas.lecture_qa import LectureSource
from app.schemas.procedure import (
    ProcedureAskRequest,
    ProcedureAskResponse,
    ProcedureSource,
)
from app.services.lecture_verifier_service import (
    LectureVerificationResult,
    LectureVerifierError,
    LectureVerifierService,
)
from app.services.procedure_answerer_service import (
    ProcedureAnswerDraft,
    ProcedureAnswererError,
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
DEFAULT_BACKEND_FAILURE_FALLBACK = (
    "回答生成中にエラーが発生しました。"
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
        verifier: LectureVerifierService,
        retrieval_limit: int = DEFAULT_RETRIEVAL_LIMIT,
        no_source_fallback: str = DEFAULT_NO_SOURCE_FALLBACK,
        no_source_action_next: str = DEFAULT_NO_SOURCE_ACTION_NEXT,
        backend_failure_fallback: str = DEFAULT_BACKEND_FAILURE_FALLBACK,
    ) -> None:
        self._db = db
        self._retriever = retriever
        self._answerer = answerer
        self._verifier = verifier
        self._retrieval_limit = max(1, retrieval_limit)
        self._no_source_fallback = no_source_fallback
        self._no_source_action_next = no_source_action_next
        self._backend_failure_fallback = backend_failure_fallback

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
                outcome_reason="no_source",
            )
            return response

        try:
            draft = await self._answerer.answer(
                query=request.query,
                lang_mode=request.lang_mode,
                sources=sources,
            )
            verification = await self._safe_verify(
                question=request.query,
                answer=draft.answer,
                sources=sources,
            )
            outcome_reason = "verified"

            if not verification.passed:
                repaired = await self._safe_repair(
                    question=request.query,
                    answer=draft.answer,
                    sources=sources,
                    unsupported_claims=verification.unsupported_claims,
                )
                if repaired:
                    draft = ProcedureAnswerDraft(
                        answer=repaired,
                        confidence="medium",
                        action_next=draft.action_next,
                    )
                    verification = await self._safe_verify(
                        question=request.query,
                        answer=repaired,
                        sources=sources,
                    )
                    outcome_reason = "repaired_verified"

            if verification.passed:
                response = self._build_success_response(
                    draft=draft,
                    sources=sources,
                )
            else:
                response = self._build_verification_failed_response(sources=sources)
                outcome_reason = "verification_failed"
        except ProcedureAnswererError:
            response = self._build_local_grounded_response(sources=sources)
            outcome_reason = "answerer_error"

        await self._persist_turn(
            question=request.query,
            response=response,
            latency_ms=self._to_latency_ms(started_at),
            outcome_reason=outcome_reason,
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

    def _build_local_grounded_response(
        self, *, sources: list[ProcedureSource]
    ) -> ProcedureAskResponse:
        excerpts = [
            f"[{source.source_id}] {source.title}（{source.section}）: {source.snippet}"
            for source in sources[:2]
            if source.snippet.strip()
        ]
        if not excerpts:
            return ProcedureAskResponse(
                answer=self._backend_failure_fallback,
                confidence="low",
                sources=sources,
                action_next=self._no_source_action_next,
                fallback=self._backend_failure_fallback,
            )

        joined_excerpt = " / ".join(excerpts)
        return ProcedureAskResponse(
            answer=f"根拠資料から確認できる内容です。{joined_excerpt}",
            confidence="low",
            sources=sources,
            action_next=self._no_source_action_next,
            fallback="",
        )

    def _build_verification_failed_response(
        self, *, sources: list[ProcedureSource]
    ) -> ProcedureAskResponse:
        return ProcedureAskResponse(
            answer=self._backend_failure_fallback,
            confidence="low",
            sources=sources,
            action_next=self._no_source_action_next,
            fallback=self._backend_failure_fallback,
        )

    async def _safe_verify(
        self,
        *,
        question: str,
        answer: str,
        sources: list[ProcedureSource],
    ) -> LectureVerificationResult:
        try:
            return await self._verifier.verify(
                question=question,
                answer=answer,
                sources=self._to_lecture_sources(sources),
            )
        except LectureVerifierError:
            return LectureVerificationResult(
                passed=False,
                summary="検証中にエラーが発生しました。",
                unsupported_claims=[answer],
            )

    async def _safe_repair(
        self,
        *,
        question: str,
        answer: str,
        sources: list[ProcedureSource],
        unsupported_claims: list[str],
    ) -> str | None:
        try:
            return await self._verifier.repair_answer(
                question=question,
                answer=answer,
                sources=self._to_lecture_sources(sources),
                unsupported_claims=unsupported_claims,
            )
        except LectureVerifierError:
            return None

    @staticmethod
    def _to_lecture_sources(sources: list[ProcedureSource]) -> list[LectureSource]:
        return [
            LectureSource(
                chunk_id=source.source_id,
                type="speech",
                text=f"{source.title}（{source.section}）: {source.snippet}",
                bm25_score=1.0,
            )
            for source in sources
        ]

    async def _persist_turn(
        self,
        *,
        question: str,
        response: ProcedureAskResponse,
        latency_ms: int,
        outcome_reason: str,
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
            verifier_supported=True,
            outcome_reason=outcome_reason,
        )
        self._db.add(qa_turn)
        await self._db.flush()

    @staticmethod
    def _to_latency_ms(started_at: float) -> int:
        elapsed = perf_counter() - started_at
        return max(0, int(elapsed * 1000))

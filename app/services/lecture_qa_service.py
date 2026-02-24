"""Lecture QA orchestration service."""

from __future__ import annotations

import re
from time import perf_counter
from typing import Literal, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_session import LectureSession
from app.models.qa_turn import QATurn
from app.schemas.lecture_qa import (
    LectureAskResponse,
    LectureFollowupResponse,
    LectureSource,
)
from app.services.lecture_answerer_service import (
    LectureAnswerDraft,
    LectureAnswererError,
    LectureAnswererService,
)
from app.services.lecture_followup_service import (
    LectureFollowupService,
)
from app.services.lecture_live_service import LectureSessionNotFoundError
from app.services.lecture_retrieval_service import LectureRetrievalService
from app.services.lecture_verifier_service import (
    LectureVerificationResult,
    LectureVerifierError,
    LectureVerifierService,
)

__all__ = ["LectureQAService", "SqlAlchemyLectureQAService"]

LECTURE_QA_FEATURE = "lecture_qa"
DEFAULT_RETRIEVAL_LIMIT = 5
DEFAULT_NO_SOURCE_FALLBACK = "講義資料に該当する情報が見つかりませんでした。"
DEFAULT_NO_SOURCE_ACTION_NEXT = "別の質問をしてください。"
DEFAULT_BACKEND_FAILURE_FALLBACK = (
    "回答生成中にエラーが発生しました。講義資料を直接確認してください。"
)


class LectureQAService(Protocol):
    """Interface for lecture QA orchestration."""

    async def ask(
        self,
        session_id: str,
        user_id: str,
        question: str,
        lang_mode: str,
        retrieval_mode: Literal["source-only", "source-plus-context"],
        top_k: int,
        context_window: int,
    ) -> LectureAskResponse:
        """Answer a lecture question with evidence-first policy."""
        ...

    async def followup(
        self,
        session_id: str,
        user_id: str,
        question: str,
        lang_mode: str,
        retrieval_mode: Literal["source-only", "source-plus-context"],
        top_k: int,
        context_window: int,
        history_turns: int,
    ) -> LectureFollowupResponse:
        """Answer a follow-up question with conversation context."""
        ...


class SqlAlchemyLectureQAService:
    """Lecture QA service with retrieval, answer, verify, and persist."""

    def __init__(
        self,
        db: AsyncSession,
        retriever: LectureRetrievalService,
        answerer: LectureAnswererService,
        verifier: LectureVerifierService,
        followup: LectureFollowupService,
        retrieval_limit: int = DEFAULT_RETRIEVAL_LIMIT,
        no_source_fallback: str = DEFAULT_NO_SOURCE_FALLBACK,
        no_source_action_next: str = DEFAULT_NO_SOURCE_ACTION_NEXT,
        backend_failure_fallback: str = DEFAULT_BACKEND_FAILURE_FALLBACK,
    ) -> None:
        self._db = db
        self._retriever = retriever
        self._answerer = answerer
        self._verifier = verifier
        self._followup = followup
        self._retrieval_limit = max(1, retrieval_limit)
        self._no_source_fallback = no_source_fallback
        self._no_source_action_next = no_source_action_next
        self._backend_failure_fallback = backend_failure_fallback

    async def ask(
        self,
        session_id: str,
        user_id: str,
        question: str,
        lang_mode: str,
        retrieval_mode: Literal["source-only", "source-plus-context"],
        top_k: int,
        context_window: int,
    ) -> LectureAskResponse:
        """Execute retrieval + answer + verify + persist."""
        await self._ensure_session_owned(session_id=session_id, user_id=user_id)
        started_at = perf_counter()
        effective_lang_mode = self._effective_lang_mode(
            lang_mode=lang_mode,
            question=question,
        )

        # Retrieve relevant sources
        sources = await self._retriever.retrieve(
            session_id=session_id,
            query=question,
            mode=retrieval_mode,
            top_k=min(top_k, self._retrieval_limit),
            context_window=context_window,
        )

        # No sources fallback
        if not sources:
            response = LectureAskResponse(
                answer=self._no_source_fallback,
                confidence="low",
                sources=[],
                verification_summary="検証用ソースがありません。",
                action_next=self._no_source_action_next,
                fallback=self._no_source_fallback,
            )
            await self._persist_turn(
                session_id=session_id,
                question=question,
                response=response,
                latency_ms=self._to_latency_ms(started_at),
            )
            return response

        # Generate answer with error handling
        try:
            draft = await self._answerer.answer(
                question=question,
                lang_mode=effective_lang_mode,
                sources=sources,
                history="",
            )
        except LectureAnswererError:
            response = self._build_local_grounded_response(
                sources=sources,
                lang_mode=effective_lang_mode,
            )
            await self._persist_turn(
                session_id=session_id,
                question=question,
                response=response,
                latency_ms=self._to_latency_ms(started_at),
            )
            return response

        # Verify answer with error handling
        verification = await self._safe_verify(
            question=question,
            answer=draft.answer,
            sources=sources,
        )

        # Handle verification failure
        if not verification.passed:
            repaired = await self._safe_repair(
                question=question,
                answer=draft.answer,
                sources=sources,
                unsupported_claims=verification.unsupported_claims,
            )
            if repaired:
                draft = LectureAnswerDraft(
                    answer=repaired,
                    confidence="medium",
                    action_next=draft.action_next,
                )
                verification = await self._safe_verify(
                    question=question,
                    answer=repaired,
                    sources=sources,
                )

        # Build response
        response = self._build_response(
            draft=draft,
            sources=sources,
            verification=verification,
        )

        # Persist turn
        await self._persist_turn(
            session_id=session_id,
            question=question,
            response=response,
            latency_ms=self._to_latency_ms(started_at),
        )

        return response

    async def followup(
        self,
        session_id: str,
        user_id: str,
        question: str,
        lang_mode: str,
        retrieval_mode: Literal["source-only", "source-plus-context"],
        top_k: int,
        context_window: int,
        history_turns: int,
    ) -> LectureFollowupResponse:
        """Answer follow-up question with conversation context."""
        await self._ensure_session_owned(session_id=session_id, user_id=user_id)
        started_at = perf_counter()
        effective_lang_mode = self._effective_lang_mode(
            lang_mode=lang_mode,
            question=question,
        )

        # Resolve follow-up to standalone query
        resolution = await self._followup.resolve_query(
            session_id=session_id,
            user_id=user_id,
            question=question,
            history_turns=history_turns,
        )

        # Retrieve using resolved query
        sources = await self._retriever.retrieve(
            session_id=session_id,
            query=resolution.standalone_query,
            mode=retrieval_mode,
            top_k=min(top_k, self._retrieval_limit),
            context_window=context_window,
        )

        # No sources fallback
        if not sources:
            response = LectureFollowupResponse(
                answer=self._no_source_fallback,
                confidence="low",
                sources=[],
                verification_summary="検証用ソースがありません。",
                action_next=self._no_source_action_next,
                fallback=self._no_source_fallback,
                resolved_query=resolution.standalone_query,
            )
            await self._persist_turn(
                session_id=session_id,
                question=question,
                response=response,
                latency_ms=self._to_latency_ms(started_at),
            )
            return response

        # Generate answer with history context and error handling
        try:
            draft = await self._answerer.answer(
                question=resolution.standalone_query,
                lang_mode=effective_lang_mode,
                sources=sources,
                history=resolution.history_context,
            )
        except LectureAnswererError:
            base_response = self._build_local_grounded_response(
                sources=sources,
                lang_mode=effective_lang_mode,
            )
            await self._persist_turn(
                session_id=session_id,
                question=question,
                response=base_response,
                latency_ms=self._to_latency_ms(started_at),
            )
            return LectureFollowupResponse(
                answer=base_response.answer,
                confidence=base_response.confidence,
                sources=base_response.sources,
                verification_summary=base_response.verification_summary,
                action_next=base_response.action_next,
                fallback=base_response.fallback,
                resolved_query=resolution.standalone_query,
            )

        # Verify answer with error handling
        verification = await self._safe_verify(
            question=resolution.standalone_query,
            answer=draft.answer,
            sources=sources,
        )

        # Handle verification failure
        if not verification.passed:
            repaired = await self._safe_repair(
                question=resolution.standalone_query,
                answer=draft.answer,
                sources=sources,
                unsupported_claims=verification.unsupported_claims,
            )
            if repaired:
                draft = LectureAnswerDraft(
                    answer=repaired,
                    confidence="medium",
                    action_next=draft.action_next,
                )
                verification = await self._safe_verify(
                    question=resolution.standalone_query,
                    answer=repaired,
                    sources=sources,
                )

        # Build response
        response = self._build_response(
            draft=draft,
            sources=sources,
            verification=verification,
        )

        # Persist turn
        await self._persist_turn(
            session_id=session_id,
            question=question,
            response=response,
            latency_ms=self._to_latency_ms(started_at),
        )

        # Return followup response with resolved query
        return LectureFollowupResponse(
            answer=response.answer,
            confidence=response.confidence,
            sources=response.sources,
            verification_summary=response.verification_summary,
            action_next=response.action_next,
            fallback=response.fallback,
            resolved_query=resolution.standalone_query,
        )

    def _build_local_grounded_response(
        self,
        *,
        sources: list[LectureSource],
        lang_mode: str,
    ) -> LectureAskResponse:
        """Build a local grounded response from sources when Azure OpenAI fails."""
        is_english = lang_mode == "en"
        snippets = [
            source.text.strip().replace("\n", " ")[:120]
            for source in sources[:2]
            if source.text.strip()
        ]
        if not snippets:
            fallback_answer = (
                "An error occurred while generating the answer. "
                "Please check the lecture materials directly."
                if is_english
                else self._backend_failure_fallback
            )
            fallback_summary = (
                "Answer generation failed."
                if is_english
                else "回答生成に失敗しました。"
            )
            fallback_action = (
                "Please ask another question."
                if is_english
                else self._no_source_action_next
            )
            return LectureAskResponse(
                answer=fallback_answer,
                confidence="low",
                sources=sources,
                verification_summary=fallback_summary,
                action_next=fallback_action,
                fallback=fallback_answer,
            )

        if len(snippets) == 1:
            answer = (
                f'The lecture materials explain that "{snippets[0]}".'
                if is_english
                else f"講義資料では「{snippets[0]}」と説明されています。"
            )
        else:
            if is_english:
                answer = (
                    f'The lecture materials explain that "{snippets[0]}" and '
                    f'"{snippets[1]}" are relevant.'
                )
            else:
                answer = (
                    f"講義資料では「{snippets[0]}」および「{snippets[1]}」"
                    "の内容が関連しています。"
                )
        verification_summary = (
            "Answer generation failed, so the response quotes the lecture materials directly."
            if is_english
            else "回答生成に失敗したため、資料から直接抜粋しました。"
        )
        action_next = (
            "Please ask another question."
            if is_english
            else self._no_source_action_next
        )
        return LectureAskResponse(
            answer=answer,
            confidence="low",
            sources=sources,
            verification_summary=verification_summary,
            action_next=action_next,
            fallback="",
        )

    @classmethod
    def _effective_lang_mode(cls, *, lang_mode: str, question: str) -> str:
        if cls._is_english_question(question):
            return "en"
        return lang_mode

    @staticmethod
    def _is_english_question(question: str) -> bool:
        stripped = question.strip()
        if not stripped:
            return False
        has_latin = bool(re.search(r"[A-Za-z]", stripped))
        has_japanese = bool(re.search(r"[ぁ-んァ-ン一-龥]", stripped))
        return has_latin and not has_japanese

    async def _safe_verify(
        self,
        *,
        question: str,
        answer: str,
        sources: list[LectureSource],
    ) -> LectureVerificationResult:
        """Safely verify answer, catching verifier errors."""
        try:
            return await self._verifier.verify(
                question=question,
                answer=answer,
                sources=sources,
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
        sources: list[LectureSource],
        unsupported_claims: list[str],
    ) -> str | None:
        """Safely repair answer, catching verifier errors."""
        try:
            return await self._verifier.repair_answer(
                question=question,
                answer=answer,
                sources=sources,
                unsupported_claims=unsupported_claims,
            )
        except LectureVerifierError:
            return None

    def _build_response(
        self,
        draft: LectureAnswerDraft,
        sources: list[LectureSource],
        verification: LectureVerificationResult,
    ) -> LectureAskResponse:
        """Build response from draft and verification."""
        return LectureAskResponse(
            answer=draft.answer,
            confidence=draft.confidence,
            sources=sources,
            verification_summary=verification.summary,
            action_next=draft.action_next,
            fallback="" if verification.passed else draft.answer,
        )

    async def _persist_turn(
        self,
        *,
        session_id: str,
        question: str,
        response: LectureAskResponse | LectureFollowupResponse,
        latency_ms: int,
    ) -> None:
        """Persist QA turn to database."""
        citations = [source.model_dump() for source in response.sources]
        source_ids = [source.chunk_id for source in response.sources]

        qa_turn = QATurn(
            session_id=session_id,
            feature=LECTURE_QA_FEATURE,
            question=question,
            answer=response.answer,
            confidence=response.confidence,
            citations_json=citations,
            retrieved_chunk_ids_json=source_ids,
            latency_ms=latency_ms,
            verifier_supported=True,  # Verifier is always used in lecture QA
        )
        self._db.add(qa_turn)
        await self._db.flush()

    async def _ensure_session_owned(self, *, session_id: str, user_id: str) -> None:
        """Validate that the session exists and is owned by the caller."""
        result = await self._db.execute(
            select(LectureSession.id).where(
                LectureSession.id == session_id,
                LectureSession.user_id == user_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise LectureSessionNotFoundError(
                f"lecture session not found: {session_id}"
            )

    @staticmethod
    def _to_latency_ms(started_at: float) -> int:
        elapsed = perf_counter() - started_at
        return max(0, int(elapsed * 1000))

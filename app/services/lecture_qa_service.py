"""Lecture QA orchestration service."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import re
from time import perf_counter
from typing import Any, Literal, Protocol

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

logger = logging.getLogger(__name__)

LECTURE_QA_FEATURE = "lecture_qa"
DEFAULT_RETRIEVAL_LIMIT = 5
DEFAULT_CITATION_LIMIT = 2
DEFAULT_NO_SOURCE_FALLBACK = "講義資料に該当する情報が見つかりませんでした。"
DEFAULT_NO_SOURCE_ACTION_NEXT = "別の質問をしてください。"
DEFAULT_BACKEND_FAILURE_FALLBACK = (
    "回答生成中にエラーが発生しました。講義資料を直接確認してください。"
)
MAX_FAILURE_REASON_CHARS = 160


@dataclass
class QAPipelineMetrics:
    """Structured per-request lecture QA metrics."""

    question_type: str = "explanation"
    retrieval_ms: int = 0
    answer_ms: int = 0
    verify_ms: int = 0
    repair_ms: int = 0
    total_llm_calls: int = 0
    verification_triggered: bool = False
    repair_triggered: bool = False
    answer_prompt_tokens: int | None = None
    answer_completion_tokens: int | None = None
    verify_prompt_tokens: int | None = None
    verify_completion_tokens: int | None = None
    repair_prompt_tokens: int | None = None
    repair_completion_tokens: int | None = None


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
        citation_limit: int = DEFAULT_CITATION_LIMIT,
        no_source_fallback: str = DEFAULT_NO_SOURCE_FALLBACK,
        no_source_action_next: str = DEFAULT_NO_SOURCE_ACTION_NEXT,
        backend_failure_fallback: str = DEFAULT_BACKEND_FAILURE_FALLBACK,
        repair_mode: Literal["always", "conditional", "off"] = "conditional",
    ) -> None:
        self._db = db
        self._retriever = retriever
        self._answerer = answerer
        self._verifier = verifier
        self._followup = followup
        self._retrieval_limit = max(1, retrieval_limit)
        self._citation_limit = max(1, citation_limit)
        self._no_source_fallback = no_source_fallback
        self._no_source_action_next = no_source_action_next
        self._backend_failure_fallback = backend_failure_fallback
        self._repair_mode = repair_mode
        self._last_pipeline_metrics: dict[str, Any] | None = None

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
        normalized_top_k = min(max(1, top_k), self._retrieval_limit)
        normalized_context_window = max(0, context_window)
        metrics = QAPipelineMetrics(question_type=self._classify_question(question))

        # Retrieve relevant sources
        retrieval_started = perf_counter()
        sources = await self._retriever.retrieve(
            session_id=session_id,
            query=question,
            mode=retrieval_mode,
            top_k=normalized_top_k,
            context_window=normalized_context_window,
        )
        metrics.retrieval_ms = self._elapsed_ms(retrieval_started)
        sources = self._select_citations(
            question=question,
            sources=sources,
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
                outcome_reason="no_source",
                metrics=metrics,
            )
            return response

        # Generate answer with error handling
        try:
            answer_started = perf_counter()
            draft = await self._answerer.answer(
                question=question,
                lang_mode=effective_lang_mode,
                sources=sources,
                history="",
            )
            metrics.answer_ms = self._elapsed_ms(answer_started)
            self._capture_usage_metrics(
                metrics,
                usage=getattr(self._answerer, "_last_usage", None),
                phase="answer",
            )
            metrics.total_llm_calls += 1
        except LectureAnswererError as exc:
            logger.warning(
                "lecture_qa_answer_generation_failed session_id=%s user_id=%s lang_mode=%s question=%r sources=%s error=%s",
                session_id,
                user_id,
                effective_lang_mode,
                question[:120],
                len(sources),
                str(exc),
                exc_info=True,
            )
            response, outcome_reason = self._build_answerer_error_response(
                question=question,
                sources=sources,
                lang_mode=effective_lang_mode,
                error_reason=str(exc),
            )
            await self._persist_turn(
                session_id=session_id,
                question=question,
                response=response,
                latency_ms=self._to_latency_ms(started_at),
                outcome_reason=outcome_reason,
                metrics=metrics,
            )
            return response

        # Verify answer with error handling
        repaired = False
        metrics.verification_triggered = True
        verify_started = perf_counter()
        verification = await self._safe_verify(
            question=question,
            answer=draft.answer,
            sources=sources,
        )
        metrics.verify_ms += self._elapsed_ms(verify_started)
        self._capture_usage_metrics(
            metrics,
            usage=getattr(self._verifier, "_last_usage", None),
            phase="verify",
        )
        metrics.total_llm_calls += 1

        # Handle verification failure
        if not verification.passed and self._should_attempt_repair(
            question=question,
            verification=verification,
        ):
            metrics.repair_triggered = True
            repair_started = perf_counter()
            repaired_answer = await self._safe_repair(
                question=question,
                answer=draft.answer,
                sources=sources,
                unsupported_claims=verification.unsupported_claims,
            )
            metrics.repair_ms += self._elapsed_ms(repair_started)
            self._capture_usage_metrics(
                metrics,
                usage=getattr(self._verifier, "_last_repair_usage", None),
                phase="repair",
            )
            metrics.total_llm_calls += 1
            if repaired_answer:
                draft = LectureAnswerDraft(
                    answer=repaired_answer,
                    confidence="medium",
                    action_next=draft.action_next,
                )
                repaired = True
                verify_started = perf_counter()
                verification = await self._safe_verify(
                    question=question,
                    answer=repaired_answer,
                    sources=sources,
                )
                metrics.verify_ms += self._elapsed_ms(verify_started)
                self._capture_usage_metrics(
                    metrics,
                    usage=getattr(self._verifier, "_last_usage", None),
                    phase="verify",
                )
                metrics.total_llm_calls += 1

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
            outcome_reason=self._verified_outcome_reason(
                passed=verification.passed,
                repaired=repaired,
            ),
            metrics=metrics,
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
        metrics = QAPipelineMetrics(question_type=self._classify_question(question))

        # Resolve follow-up to standalone query
        resolution = await self._followup.resolve_query(
            session_id=session_id,
            user_id=user_id,
            question=question,
            history_turns=history_turns,
        )
        normalized_top_k = min(max(1, top_k), self._retrieval_limit)
        normalized_context_window = max(0, context_window)

        # Retrieve using resolved query
        retrieval_started = perf_counter()
        sources = await self._retriever.retrieve(
            session_id=session_id,
            query=resolution.standalone_query,
            mode=retrieval_mode,
            top_k=normalized_top_k,
            context_window=normalized_context_window,
        )
        metrics.retrieval_ms = self._elapsed_ms(retrieval_started)
        sources = self._select_citations(
            question=resolution.standalone_query,
            sources=sources,
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
                outcome_reason="no_source",
                metrics=metrics,
            )
            return response

        # Generate answer with history context and error handling
        try:
            answer_started = perf_counter()
            draft = await self._answerer.answer(
                question=resolution.standalone_query,
                lang_mode=effective_lang_mode,
                sources=sources,
                history=resolution.history_context,
            )
            metrics.answer_ms = self._elapsed_ms(answer_started)
            self._capture_usage_metrics(
                metrics,
                usage=getattr(self._answerer, "_last_usage", None),
                phase="answer",
            )
            metrics.total_llm_calls += 1
        except LectureAnswererError as exc:
            logger.warning(
                "lecture_qa_followup_answer_generation_failed session_id=%s user_id=%s lang_mode=%s standalone_query=%r sources=%s error=%s",
                session_id,
                user_id,
                effective_lang_mode,
                resolution.standalone_query[:120],
                len(sources),
                str(exc),
                exc_info=True,
            )
            base_response, outcome_reason = self._build_answerer_error_response(
                question=resolution.standalone_query,
                sources=sources,
                lang_mode=effective_lang_mode,
                error_reason=str(exc),
            )
            await self._persist_turn(
                session_id=session_id,
                question=question,
                response=base_response,
                latency_ms=self._to_latency_ms(started_at),
                outcome_reason=outcome_reason,
                metrics=metrics,
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
        repaired = False
        metrics.verification_triggered = True
        verify_started = perf_counter()
        verification = await self._safe_verify(
            question=resolution.standalone_query,
            answer=draft.answer,
            sources=sources,
        )
        metrics.verify_ms += self._elapsed_ms(verify_started)
        self._capture_usage_metrics(
            metrics,
            usage=getattr(self._verifier, "_last_usage", None),
            phase="verify",
        )
        metrics.total_llm_calls += 1

        # Handle verification failure
        if not verification.passed and self._should_attempt_repair(
            question=resolution.standalone_query,
            verification=verification,
        ):
            metrics.repair_triggered = True
            repair_started = perf_counter()
            repaired_answer = await self._safe_repair(
                question=resolution.standalone_query,
                answer=draft.answer,
                sources=sources,
                unsupported_claims=verification.unsupported_claims,
            )
            metrics.repair_ms += self._elapsed_ms(repair_started)
            self._capture_usage_metrics(
                metrics,
                usage=getattr(self._verifier, "_last_repair_usage", None),
                phase="repair",
            )
            metrics.total_llm_calls += 1
            if repaired_answer:
                draft = LectureAnswerDraft(
                    answer=repaired_answer,
                    confidence="medium",
                    action_next=draft.action_next,
                )
                repaired = True
                verify_started = perf_counter()
                verification = await self._safe_verify(
                    question=resolution.standalone_query,
                    answer=repaired_answer,
                    sources=sources,
                )
                metrics.verify_ms += self._elapsed_ms(verify_started)
                self._capture_usage_metrics(
                    metrics,
                    usage=getattr(self._verifier, "_last_usage", None),
                    phase="verify",
                )
                metrics.total_llm_calls += 1

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
            outcome_reason=self._verified_outcome_reason(
                passed=verification.passed,
                repaired=repaired,
            ),
            metrics=metrics,
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

    def _build_answerer_error_response(
        self,
        *,
        question: str,
        sources: list[LectureSource],
        lang_mode: str,
        error_reason: str,
    ) -> tuple[LectureAskResponse, str]:
        """Build a grounded/local fallback response for answer generation failures."""
        _ = question
        is_english = lang_mode == "en"
        for source_index, source in enumerate(sources, start=1):
            grounded_answer = self._build_compact_fallback_answer(
                source=source,
                source_index=source_index,
                is_english=is_english,
            )
            if grounded_answer is None:
                continue
            verification_summary = (
                "Answer generation failed, so a grounded snippet from lecture sources was returned."
                if is_english
                else "回答生成に失敗したため、講義資料の根拠を簡易表示しました。"
            )
            action_next = (
                "Please ask another question."
                if is_english
                else self._no_source_action_next
            )
            return (
                LectureAskResponse(
                    answer=grounded_answer,
                    confidence="low",
                    sources=sources,
                    verification_summary=verification_summary,
                    action_next=action_next,
                    fallback=grounded_answer,
                ),
                "answerer_error_grounded",
            )

        failure_message = self._build_failure_message(
            is_english=is_english,
            error_reason=error_reason,
        )
        action_next = (
            "Please ask another question."
            if is_english
            else self._no_source_action_next
        )
        return (
            LectureAskResponse(
                answer=failure_message,
                confidence="low",
                sources=sources,
                verification_summary=failure_message,
                action_next=action_next,
                fallback=failure_message,
            ),
            "answerer_error_failure",
        )

    def _build_failure_message(self, *, is_english: bool, error_reason: str) -> str:
        normalized_reason = self._normalize_failure_reason(
            reason=error_reason,
            is_english=is_english,
        )
        if is_english:
            return f"Failed to generate answer. (Reason: {normalized_reason})"
        return f"回答文生成に失敗しました。（理由: {normalized_reason}）"

    @staticmethod
    def _normalize_failure_reason(*, reason: str, is_english: bool) -> str:
        normalized = re.sub(r"\s+", " ", reason).strip()
        if not normalized:
            return "unknown error" if is_english else "不明なエラー"
        if len(normalized) <= MAX_FAILURE_REASON_CHARS:
            return normalized
        return normalized[:MAX_FAILURE_REASON_CHARS].rstrip()

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
            confidence=draft.confidence if verification.passed else "low",
            sources=sources,
            verification_summary=verification.summary,
            action_next=draft.action_next,
            fallback="" if verification.passed else draft.answer,
        )

    def _select_citations(
        self,
        *,
        question: str,
        sources: list[LectureSource],
    ) -> list[LectureSource]:
        if not sources:
            return []

        question_terms = self._tokenize_for_overlap(question)
        deduped: list[LectureSource] = []
        seen_keys: set[str] = set()
        for source in sources:
            normalized_text = source.text.strip().lower()
            key = normalized_text if normalized_text else source.chunk_id
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(source)

        ranked_sources = sorted(
            deduped,
            key=lambda source: (
                1 if source.is_direct_hit else 0,
                self._term_overlap_score(question_terms, source.text),
                source.bm25_score,
            ),
            reverse=True,
        )
        return ranked_sources[: self._citation_limit]

    def _build_compact_fallback_answer(
        self,
        *,
        source: LectureSource,
        source_index: int,
        is_english: bool,
    ) -> str | None:
        chunk_label = self._source_display_label(
            source=source, source_index=source_index
        )

        compact_snippet = source.text.strip().replace("\n", " ")[:100]
        if not compact_snippet:
            return None
        if is_english:
            return f"According to {chunk_label}, {compact_snippet}."
        return f"{chunk_label}によると、{compact_snippet}。"

    @staticmethod
    def _source_display_label(*, source: LectureSource, source_index: int) -> str:
        normalized_chunk_id = source.chunk_id.strip()
        if re.fullmatch(r"[SV]-\d{3}", normalized_chunk_id):
            return f"ID {normalized_chunk_id}"

        prefix = "S" if source.type == "speech" else "V"
        normalized_index = max(1, source_index)
        return f"ID {prefix}-{normalized_index:03d}"

    @staticmethod
    def _tokenize_for_overlap(text: str) -> set[str]:
        normalized = text.lower()
        tokens = {
            token
            for token in re.findall(r"[A-Za-z0-9]+|[ぁ-んァ-ン一-龥]+", normalized)
            if len(token) > 1
        }
        ja_chars = "".join(re.findall(r"[ぁ-んァ-ン一-龥]", normalized))
        tokens.update(ja_chars[i : i + 2] for i in range(max(0, len(ja_chars) - 1)))
        return tokens

    @classmethod
    def _term_overlap_score(cls, question_terms: set[str], source_text: str) -> float:
        if not question_terms:
            return 0.0
        source_terms = cls._tokenize_for_overlap(source_text)
        if not source_terms:
            return 0.0
        overlap = question_terms & source_terms
        return float(len(overlap))

    async def _persist_turn(
        self,
        *,
        session_id: str,
        question: str,
        response: LectureAskResponse | LectureFollowupResponse,
        latency_ms: int,
        outcome_reason: str,
        metrics: QAPipelineMetrics,
    ) -> None:
        """Persist QA turn to database."""
        citations = [source.model_dump() for source in response.sources]
        source_ids = [source.chunk_id for source in response.sources]
        metrics_payload = asdict(metrics)
        self._last_pipeline_metrics = metrics_payload

        qa_turn = QATurn(
            session_id=session_id,
            feature=LECTURE_QA_FEATURE,
            question=question,
            answer=response.answer,
            confidence=response.confidence,
            citations_json=citations,
            retrieved_chunk_ids_json=source_ids,
            metrics_json=metrics_payload,
            latency_ms=latency_ms,
            verifier_supported=True,  # Verifier is always used in lecture QA
            outcome_reason=outcome_reason,
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

    @staticmethod
    def _verified_outcome_reason(*, passed: bool, repaired: bool) -> str:
        if not passed:
            return "verification_failed"
        if repaired:
            return "repaired_verified"
        return "verified"

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(0, int((perf_counter() - started_at) * 1000))

    def _should_attempt_repair(
        self,
        *,
        question: str,
        verification: LectureVerificationResult,
    ) -> bool:
        if verification.passed or not verification.unsupported_claims:
            return False
        if self._repair_mode == "off":
            return False
        if self._repair_mode == "always":
            return True
        return self._is_high_risk_question(question)

    @staticmethod
    def _classify_question(question: str) -> str:
        if SqlAlchemyLectureQAService._is_high_risk_question(question):
            return "factoid"
        return "explanation"

    @staticmethod
    def _is_high_risk_question(question: str) -> bool:
        normalized = question.strip().lower()
        patterns = (
            r"いつ",
            r"誰",
            r"何年",
            r"何月",
            r"何日",
            r"何時",
            r"何分",
            r"何人",
            r"いくつ",
            r"どれくらい",
            r"\bwhen\b",
            r"\bwho\b",
            r"\bhow many\b",
            r"\bhow much\b",
            r"\bwhat year\b",
            r"\bwhat date\b",
        )
        return any(re.search(pattern, normalized) for pattern in patterns) or bool(
            re.search(r"\d{1,4}", normalized)
        )

    @staticmethod
    def _capture_usage_metrics(
        metrics: QAPipelineMetrics,
        *,
        usage: Any,
        phase: Literal["answer", "verify", "repair"],
    ) -> None:
        if usage is None:
            return
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        if phase == "answer":
            metrics.answer_prompt_tokens = prompt_tokens
            metrics.answer_completion_tokens = completion_tokens
        elif phase == "verify":
            metrics.verify_prompt_tokens = prompt_tokens
            metrics.verify_completion_tokens = completion_tokens
        else:
            metrics.repair_prompt_tokens = prompt_tokens
            metrics.repair_completion_tokens = completion_tokens

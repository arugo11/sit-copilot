"""Observed wrapper for LectureQAService with Weave tracking."""

from __future__ import annotations

import logging
import time
from typing import Literal

from app.schemas.lecture_qa import (
    LectureAskResponse,
    LectureFollowupResponse,
)
from app.services.lecture_qa_service import LectureQAService
from app.services.observability.weave_observer_service import WeaveObserverService

__all__ = ["ObservedLectureQAService"]

logger = logging.getLogger(__name__)

# Feature identifier for Weave tracking
LECTURE_QA_FEATURE = "lecture-qa"


class ObservedLectureQAService:
    """Observed wrapper for SqlAlchemyLectureQAService.

    Tracks QA turn interactions via Weave observer.
    Observer failures never block the main QA flow.
    """

    __slots__ = ("_inner", "_observer")

    def __init__(
        self,
        inner: LectureQAService,
        observer: WeaveObserverService,
    ) -> None:
        """Initialize observed QA service.

        Args:
            inner: The underlying LectureQAService
            observer: Weave observer service
        """
        self._inner = inner
        self._observer = observer

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
        """Answer a lecture question with QA turn tracking.

        Args:
            session_id: Lecture session ID
            user_id: User ID for ownership validation
            question: User question
            lang_mode: Language mode
            retrieval_mode: Retrieval mode
            top_k: Number of sources to retrieve
            context_window: Context window size

        Returns:
            Lecture ask response with answer and sources
        """
        start_time = time.perf_counter()

        # Call inner service
        result = await self._inner.ask(
            session_id=session_id,
            user_id=user_id,
            question=question,
            lang_mode=lang_mode,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            context_window=context_window,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Track QA turn (non-blocking via dispatcher)
        await self._track_qa_turn(
            session_id=session_id,
            question=question,
            response=result,
            latency_ms=latency_ms,
            retrieval_mode=retrieval_mode,
        )

        return result

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
        """Answer a follow-up question with QA turn tracking.

        Args:
            session_id: Lecture session ID
            user_id: User ID for ownership validation
            question: User question
            lang_mode: Language mode
            retrieval_mode: Retrieval mode
            top_k: Number of sources to retrieve
            context_window: Context window size
            history_turns: Number of history turns to include

        Returns:
            Lecture followup response with answer and sources
        """
        start_time = time.perf_counter()

        # Call inner service
        result = await self._inner.followup(
            session_id=session_id,
            user_id=user_id,
            question=question,
            lang_mode=lang_mode,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            context_window=context_window,
            history_turns=history_turns,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Track QA turn (non-blocking via dispatcher)
        await self._track_qa_turn(
            session_id=session_id,
            question=question,
            response=result,
            latency_ms=latency_ms,
            retrieval_mode=retrieval_mode,
        )

        return result

    async def _track_qa_turn(
        self,
        session_id: str,
        question: str,
        response: LectureAskResponse | LectureFollowupResponse,
        latency_ms: int,
        retrieval_mode: str,
    ) -> None:
        """Track QA turn via observer (fire-and-forget).

        Args:
            session_id: Lecture session ID
            question: User question
            response: Generated response
            latency_ms: Generation latency in milliseconds
            retrieval_mode: Retrieval mode used
        """
        # Build citations list from sources
        citations = [
            {
                "chunk_id": source.chunk_id,
                "type": source.type,
                "timestamp": source.timestamp,
                "text": source.text[:200] + "..."
                if len(source.text) > 200
                else source.text,
                "bm25_score": source.bm25_score,
                "is_direct_hit": source.is_direct_hit,
            }
            for source in response.sources
        ]

        # Extract chunk IDs
        retrieved_chunk_ids = [source.chunk_id for source in response.sources]

        # Determine outcome reason
        outcome_reason = self._determine_outcome_reason(response)
        metrics = getattr(self._inner, "_last_pipeline_metrics", None)

        try:
            await self._observer.track_qa_turn(
                session_id=session_id,
                feature=LECTURE_QA_FEATURE,
                question=question,
                answer=response.answer,
                confidence=response.confidence,
                citations=citations,
                retrieved_chunk_ids=retrieved_chunk_ids,
                latency_ms=latency_ms,
                verifier_supported=True,  # Lecture QA always uses verifier
                outcome_reason=outcome_reason,
                metadata=metrics if isinstance(metrics, dict) else None,
            )
        except Exception:
            # Observer failures never block main flow
            logger.debug(
                "weave_observer_qa_turn_tracking_failed session_id=%s", session_id
            )

    def _determine_outcome_reason(
        self, response: LectureAskResponse | LectureFollowupResponse
    ) -> str:
        """Determine outcome reason based on response characteristics.

        Args:
            response: Generated response

        Returns:
            Outcome reason string
        """
        if response.fallback:
            return "fallback_used"

        if not response.sources:
            return "no_sources"

        if response.confidence == "high":
            return "high_confidence_direct_match"
        elif response.confidence == "medium":
            return "medium_confidence_context_match"
        else:
            return "low_confidence_weak_match"

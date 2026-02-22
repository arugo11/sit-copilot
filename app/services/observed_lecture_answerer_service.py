"""Observed wrapper for LectureAnswererService with Weave tracking."""

from __future__ import annotations

import logging
import time

from app.schemas.lecture_qa import LectureSource
from app.services.lecture_answerer_service import (
    LectureAnswerDraft,
    LectureAnswererError,
    LectureAnswererService,
)
from app.services.observability.weave_observer_service import WeaveObserverService

__all__ = ["ObservedLectureAnswererService"]

logger = logging.getLogger(__name__)

# Azure OpenAI provider identifier for Weave
AZURE_OPENAI_PROVIDER = "azure-openai"


class ObservedLectureAnswererService:
    """Observed wrapper for AzureOpenAILectureAnswererService.

    Tracks LLM calls to Azure OpenAI via Weave observer.
    Observer failures never block the main answer generation flow.
    """

    __slots__ = ("_inner", "_observer", "_model")

    def __init__(
        self,
        inner: LectureAnswererService,
        observer: WeaveObserverService,
        model: str = "gpt-5-nano",
    ) -> None:
        """Initialize observed answerer service.

        Args:
            inner: The underlying LectureAnswererService
            observer: Weave observer service
            model: Model name for tracking
        """
        self._inner = inner
        self._observer = observer
        self._model = model

    async def answer(
        self,
        question: str,
        lang_mode: str,
        sources: list[LectureSource],
        history: str = "",
    ) -> LectureAnswerDraft:
        """Generate grounded answer with LLM call tracking.

        Args:
            question: User question
            lang_mode: Language mode (ja, easy-ja, en)
            sources: Retrieved lecture chunks
            history: Conversation history for context

        Returns:
            Draft answer with confidence and action next

        Raises:
            LectureAnswererError: If answer generation fails
        """
        start_time = time.perf_counter()

        # Build prompt for tracking (truncate if needed)
        prompt = self._build_prompt_for_tracking(
            question=question,
            lang_mode=lang_mode,
            sources=sources,
            history=history,
        )

        try:
            # Call inner service
            result = await self._inner.answer(question, lang_mode, sources, history)

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Track successful LLM call (non-blocking via dispatcher)
            await self._track_llm_call(
                prompt=prompt,
                response=result.answer,
                latency_ms=latency_ms,
                outcome="success",
            )

            return result

        except LectureAnswererError as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Track failed LLM call
            await self._track_llm_call(
                prompt=prompt,
                response=f"ERROR: {exc}",
                latency_ms=latency_ms,
                outcome="error",
            )

            raise

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Track unexpected error
            await self._track_llm_call(
                prompt=prompt,
                response=f"UNEXPECTED ERROR: {exc}",
                latency_ms=latency_ms,
                outcome="error",
            )

            raise

    async def _track_llm_call(
        self,
        prompt: str,
        response: str,
        latency_ms: int,
        outcome: str,
    ) -> None:
        """Track LLM call via observer (fire-and-forget).

        Args:
            prompt: Input prompt
            response: Model response or error message
            latency_ms: API latency in milliseconds
            outcome: Operation outcome (success or error)
        """
        metadata = {
            "outcome": outcome,
            "operation": "lecture.answer.generate",
            "lang_mode": getattr(self, "_last_lang_mode", "unknown"),
        }

        try:
            await self._observer.track_llm_call(
                provider=AZURE_OPENAI_PROVIDER,
                model=self._model,
                prompt=prompt,
                response=response,
                latency_ms=latency_ms,
                tokens_prompt=None,  # Azure OpenAI doesn't return token count by default
                tokens_completion=None,
                metadata=metadata,
            )
        except Exception:
            # Observer failures never block main flow
            logger.debug("weave_observer_llm_call_tracking_failed outcome=%s", outcome)

    def _build_prompt_for_tracking(
        self,
        question: str,
        lang_mode: str,
        sources: list[LectureSource],
        history: str,
    ) -> str:
        """Build a truncated prompt representation for tracking.

        Args:
            question: User question
            lang_mode: Language mode
            sources: Retrieved sources
            history: Conversation history

        Returns:
            Truncated prompt string
        """
        # Store lang_mode for metadata
        self._last_lang_mode = lang_mode  # noqa: SF01

        # Build sources preview (limit for tracking)
        source_count = len(sources)
        max_sources_preview = 2
        sources_preview = []

        for i, source in enumerate(sources[:max_sources_preview]):
            ts = source.timestamp or "??:??"
            # Truncate source text
            text_preview = (
                source.text[:100] + "..." if len(source.text) > 100 else source.text
            )
            sources_preview.append(f"{i + 1}. [{ts}] {text_preview}")

        if source_count > max_sources_preview:
            sources_preview.append(
                f"... ({source_count - max_sources_preview} more sources)"
            )

        sources_text = "\n".join(sources_preview) if sources_preview else "(no sources)"

        history_section = f"\n\n会話履歴:\n{history[:200]}..." if history else ""

        return (
            "あなたは講義内容に基づいて質問に答えるアシスタントです。\n\n"
            f"講義資料:\n{sources_text}"
            f"{history_section}\n\n"
            f"質問: {question}\n\n"
            "回答のガイドライン:\n"
            "- 講義資料に基づいて回答してください\n"
            "- 具体的な時間（例: 05:23）を引用して説明してください\n"
            "- 資料にない情報は「資料に記載がありません」と明示してください\n"
            "- 簡潔に回答してください（3-5文程度）"
        )

"""Weave observer service protocol and implementations."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol, runtime_checkable

from app.services.observability.llm_usage import MODEL_COSTS
from app.services.observability.weave_dispatcher import WeaveDispatcher

__all__ = [
    "WeaveObserverService",
    "NoopWeaveObserverService",
    "WandBWeaveObserverService",
]

logger = logging.getLogger(__name__)


@runtime_checkable
class WeaveObserverService(Protocol):
    """Protocol for Weave observability operations.

    All methods must be non-blocking and error-isolated.
    Observability failures should never affect business logic.
    """

    async def track_qa_turn(
        self,
        session_id: str,
        feature: str,
        question: str,
        answer: str,
        confidence: str,
        citations: list[dict[str, Any]],
        retrieved_chunk_ids: list[str],
        latency_ms: int,
        verifier_supported: bool,
        outcome_reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Track a QA turn interaction.

        Args:
            session_id: Lecture or procedure session ID
            feature: Feature name (e.g., "lecture-qa", "procedure-qa")
            question: User question
            answer: Generated answer
            confidence: Confidence level (e.g., "high", "medium", "low")
            citations: Source citations
            retrieved_chunk_ids: Retrieved chunk IDs for context
            latency_ms: Generation latency in milliseconds
            verifier_supported: Whether verifier was used
            outcome_reason: Outcome reason or status
            metadata: Optional structured QA metrics
        """
        ...

    async def track_llm_call(
        self,
        provider: str,
        model: str,
        prompt: str,
        response: str,
        latency_ms: int,
        tokens_prompt: int | None = None,
        tokens_completion: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Track an LLM API call.

        Args:
            provider: LLM provider (e.g., "azure-openai", "openai")
            model: Model name (e.g., "gpt-5-nano")
            prompt: Input prompt
            response: Model response
            latency_ms: API latency in milliseconds
            tokens_prompt: Input token count
            tokens_completion: Output token count
            metadata: Additional metadata
        """
        ...

    async def track_ocr_with_image(
        self,
        session_id: str,
        timestamp_ms: int,
        source: str,
        ocr_text: str,
        ocr_confidence: float,
        quality: str,
        change_score: float,
        image_bytes: bytes | None = None,
        blob_path: str | None = None,
    ) -> None:
        """Track OCR event with optional image preview.

        Args:
            session_id: Lecture session ID
            timestamp_ms: Event timestamp in milliseconds
            source: OCR source (e.g., "azure-vision")
            ocr_text: Extracted text
            ocr_confidence: OCR confidence score
            quality: Image quality assessment
            change_score: Slide change detection score
            image_bytes: Raw image bytes for preview (if enabled)
            blob_path: Storage blob path
        """
        ...

    async def track_slide_transition(
        self,
        session_id: str,
        timestamp_ms: int,
        slide_number: int,
        ocr_text: str,
        image_bytes: bytes | None = None,
        blob_path: str | None = None,
    ) -> None:
        """Track slide transition event.

        Args:
            session_id: Lecture session ID
            timestamp_ms: Event timestamp in milliseconds
            slide_number: Slide sequence number
            ocr_text: Extracted OCR text
            image_bytes: Slide image bytes for preview
            blob_path: Storage blob path
        """
        ...

    async def track_speech_event(
        self,
        session_id: str,
        start_ms: int,
        end_ms: int,
        text: str,
        original_text: str | None,
        confidence: float,
        is_final: bool,
        speaker: str,
    ) -> None:
        """Track speech-to-text event.

        Args:
            session_id: Lecture session ID
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
            text: Corrected text
            original_text: Original ASR output
            confidence: ASR confidence score
            is_final: Whether this is a final result
            speaker: Speaker identifier
        """
        ...

    def with_session_context(
        self,
        session_id: str,
    ) -> AsyncIterator:
        """Create a context manager that sets session context for all spans.

        Args:
            session_id: Session ID to propagate to all child spans

        Returns:
            Async context manager
        """
        ...


class NoopWeaveObserverService:
    """No-op implementation for testing or when Weave is disabled."""

    __slots__ = ()

    async def track_qa_turn(
        self,
        session_id: str,
        feature: str,
        question: str,
        answer: str,
        confidence: str,
        citations: list[dict[str, Any]],
        retrieved_chunk_ids: list[str],
        latency_ms: int,
        verifier_supported: bool,
        outcome_reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """No-op QA turn tracking."""
        _ = metadata

    async def track_llm_call(
        self,
        provider: str,
        model: str,
        prompt: str,
        response: str,
        latency_ms: int,
        tokens_prompt: int | None = None,
        tokens_completion: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """No-op LLM call tracking."""

    async def track_ocr_with_image(
        self,
        session_id: str,
        timestamp_ms: int,
        source: str,
        ocr_text: str,
        ocr_confidence: float,
        quality: str,
        change_score: float,
        image_bytes: bytes | None = None,
        blob_path: str | None = None,
    ) -> None:
        """No-op OCR tracking."""

    async def track_slide_transition(
        self,
        session_id: str,
        timestamp_ms: int,
        slide_number: int,
        ocr_text: str,
        image_bytes: bytes | None = None,
        blob_path: str | None = None,
    ) -> None:
        """No-op slide transition tracking."""

    async def track_speech_event(
        self,
        session_id: str,
        start_ms: int,
        end_ms: int,
        text: str,
        original_text: str | None,
        confidence: float,
        is_final: bool,
        speaker: str,
    ) -> None:
        """No-op speech event tracking."""

    @asynccontextmanager
    async def with_session_context(
        self,
        session_id: str,
    ) -> AsyncIterator[None]:
        """No-op context manager."""
        yield


def _safe_log_error(message: str, exc: Exception | None = None) -> None:
    """Safely log errors without disrupting application flow.

    Args:
        message: Error message to log
        exc: Optional exception
    """
    if exc:
        logger.debug(message, exc_info=exc)
    else:
        logger.debug(message)


class WandBWeaveObserverService:
    """WandB Weave observer implementation.

    Uses fire-and-forget pattern with a dispatcher queue.
    All operations are non-blocking and error-isolated.
    """

    __slots__ = (
        "_settings",
        "_weave",
        "_dispatcher_value",
    )

    def __init__(self, settings: Any) -> None:
        """Initialize Weave observer service.

        Args:
            settings: WeaveSettings instance from config
        """
        self._settings = settings
        self._dispatcher_value = WeaveDispatcher(settings)
        self._weave = _import_weave()

    @property
    def _dispatcher(self) -> WeaveDispatcher:
        """Get the dispatcher instance."""
        return self._dispatcher_value

    async def track_qa_turn(
        self,
        session_id: str,
        feature: str,
        question: str,
        answer: str,
        confidence: str,
        citations: list[dict[str, Any]],
        retrieved_chunk_ids: list[str],
        latency_ms: int,
        verifier_supported: bool,
        outcome_reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Track QA turn via dispatcher queue."""

        @self._weave.op(name="qa_turn")
        async def _track() -> dict[str, Any]:
            return {
                "session_id": session_id,
                "feature": feature,
                "question": question
                if self._settings.capture_prompts
                else "[REDACTED]",
                "answer": answer if self._settings.capture_responses else "[REDACTED]",
                "confidence": confidence,
                "citations": citations,
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "latency_ms": latency_ms,
                "verifier_supported": verifier_supported,
                "outcome_reason": outcome_reason,
            }
            if metadata:
                data["metadata"] = metadata
            return data

        try:
            await self._dispatcher.dispatch(_track)
        except Exception:
            # Queue full - skip tracking
            pass

    async def track_llm_call(
        self,
        provider: str,
        model: str,
        prompt: str,
        response: str,
        latency_ms: int,
        tokens_prompt: int | None = None,
        tokens_completion: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Track LLM call via dispatcher queue."""

        @self._weave.op(name="llm_call")
        async def _track() -> dict[str, Any]:
            data: dict[str, Any] = {
                "provider": provider,
                "model": model,
                "latency_ms": latency_ms,
            }
            if self._settings.capture_prompts:
                data["prompt"] = prompt
            if self._settings.capture_responses:
                data["response"] = response
            if tokens_prompt is not None:
                data["tokens_prompt"] = tokens_prompt
            if tokens_completion is not None:
                data["tokens_completion"] = tokens_completion

            # Compute per-call cost using registered model pricing
            if tokens_prompt is not None and tokens_completion is not None:
                cost_info = MODEL_COSTS.get(model)
                if cost_info:
                    prompt_cost = tokens_prompt * cost_info["prompt"]
                    completion_cost = tokens_completion * cost_info["completion"]
                    data["prompt_cost_usd"] = prompt_cost
                    data["completion_cost_usd"] = completion_cost
                    data["total_cost_usd"] = prompt_cost + completion_cost

            if metadata:
                data["metadata"] = metadata
            return data

        try:
            await self._dispatcher.dispatch(_track)
        except Exception:
            pass

    async def track_ocr_with_image(
        self,
        session_id: str,
        timestamp_ms: int,
        source: str,
        ocr_text: str,
        ocr_confidence: float,
        quality: str,
        change_score: float,
        image_bytes: bytes | None = None,
        blob_path: str | None = None,
    ) -> None:
        """Track OCR event with optional image preview via dispatcher queue."""

        @self._weave.op(name="vision_ocr_extract")
        async def _track() -> dict[str, Any]:
            data: dict[str, Any] = {
                "session_id": session_id,
                "timestamp_ms": timestamp_ms,
                "source": source,
                "ocr_text": ocr_text,
                "ocr_confidence": ocr_confidence,
                "quality": quality,
                "change_score": change_score,
                "blob_path": blob_path,
            }
            if (
                self._settings.capture_images
                and image_bytes
                and len(image_bytes) <= self._settings.max_image_size_bytes
            ):
                try:
                    data["image_preview"] = self._weave.Image.from_bytes(image_bytes)
                except Exception:
                    pass
            return data

        try:
            await self._dispatcher.dispatch(_track)
        except Exception:
            pass

    async def track_slide_transition(
        self,
        session_id: str,
        timestamp_ms: int,
        slide_number: int,
        ocr_text: str,
        image_bytes: bytes | None = None,
        blob_path: str | None = None,
    ) -> None:
        """Track slide transition via dispatcher queue."""

        @self._weave.op(name="slide_transition")
        async def _track() -> dict[str, Any]:
            data: dict[str, Any] = {
                "session_id": session_id,
                "timestamp_ms": timestamp_ms,
                "slide_number": slide_number,
                "ocr_text": ocr_text,
                "blob_path": blob_path,
            }
            if (
                self._settings.capture_images
                and image_bytes
                and len(image_bytes) <= self._settings.max_image_size_bytes
            ):
                try:
                    data["slide_image"] = self._weave.Image.from_bytes(image_bytes)
                except Exception:
                    pass
            return data

        try:
            await self._dispatcher.dispatch(_track)
        except Exception:
            pass

    async def track_speech_event(
        self,
        session_id: str,
        start_ms: int,
        end_ms: int,
        text: str,
        original_text: str | None,
        confidence: float,
        is_final: bool,
        speaker: str,
    ) -> None:
        """Track speech event via dispatcher queue."""

        @self._weave.op(name="speech_to_text")
        async def _track() -> dict[str, Any]:
            data: dict[str, Any] = {
                "session_id": session_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text,
                "confidence": confidence,
                "is_final": is_final,
                "speaker": speaker,
            }
            if original_text is not None:
                data["original_text"] = original_text
            return data

        try:
            await self._dispatcher.dispatch(_track)
        except Exception:
            pass

    @asynccontextmanager
    async def with_session_context(
        self,
        session_id: str,
    ) -> AsyncIterator[None]:
        """Create a context manager that sets session context for all spans."""
        # For now, just yield without special context handling
        # The session_id is passed directly to track_* methods
        yield


def _import_weave():
    """Lazy import weave module."""
    try:
        import weave

        return weave
    except ImportError:
        # Return no-op module if weave is not installed
        return _NoopWeave()


class _NoopWeave:
    """No-op weave placeholder for when module is not installed."""

    class _NoopOp:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            pass

        def __call__(self, func):
            return func

    class Image:
        @staticmethod
        def from_bytes(_data):
            return None

    op = _NoopOp

"""Observed wrapper for Lecture Summary Generator service with Weave tracking."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import TYPE_CHECKING

from app.services.lecture_summary_generator_service import (
    LectureSummaryGeneratorService,
    LectureSummaryResult,
)
from app.services.observability import WeaveObserverService

__all__ = [
    "ObservedLectureSummaryGeneratorService",
    "ObservedLectureSummaryGeneratorServiceError",
]

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.models.speech_event import SpeechEvent
    from app.models.visual_event import VisualEvent


class ObservedLectureSummaryGeneratorServiceError(Exception):
    """Raised when observed summary generator service wrapper fails."""


class ObservedLectureSummaryGeneratorService:
    """Observed wrapper for LLM-powered summary generation."""

    def __init__(
        self,
        inner: LectureSummaryGeneratorService,
        observer: WeaveObserverService,
    ) -> None:
        """Initialize observed summary generator service.

        Args:
            inner: Underlying summary generator service implementation
            observer: Weave observer service for tracking
        """
        self._inner = inner
        self._observer = observer

    async def generate_summary(
        self,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
        lang_mode: str,
    ) -> LectureSummaryResult:
        """Generate LLM summary with observation tracking."""
        start_time = perf_counter()

        # Build prompt excerpt for tracking
        speech_text = " ".join([e.text for e in speech_events[-3:]])
        visual_text = " ".join([e.ocr_text for e in visual_events[-2:]])
        prompt_excerpt = (
            f"Speech: {speech_text[:200]}... Visual: {visual_text[:200]}..."
        )

        # Call inner service
        result = await self._inner.generate_summary(
            speech_events, visual_events, lang_mode
        )

        latency_ms = int((perf_counter() - start_time) * 1000)

        # Determine model name
        model = getattr(self._inner, "_model", "gpt-5-nano")

        # Track LLM summary generation
        await self._observer.track_llm_call(
            provider="azure-openai",
            model=model,
            prompt=prompt_excerpt,
            response=result.summary[:500],
            latency_ms=latency_ms,
            metadata={
                "lang_mode": lang_mode,
                "speech_count": len(speech_events),
                "visual_count": len(visual_events),
                "key_terms_count": len(result.key_terms),
                "evidence_tags_count": len(result.evidence_tags),
            },
        )

        return result

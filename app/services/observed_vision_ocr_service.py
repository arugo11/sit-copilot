"""Observed wrapper for Vision OCR service with Weave tracking."""

from __future__ import annotations

import logging

from app.schemas.lecture import LectureVisualSource
from app.services.observability import WeaveObserverService
from app.services.vision_ocr_service import VisionOCRResult, VisionOCRService

__all__ = ["ObservedVisionOCRService", "ObservedVisionOCRServiceError"]

logger = logging.getLogger(__name__)


class ObservedVisionOCRServiceError(Exception):
    """Raised when observed OCR wrapper fails."""


class ObservedVisionOCRService:
    """Observed wrapper for Vision OCR with image display in Weave UI."""

    def __init__(
        self,
        inner: VisionOCRService,
        observer: WeaveObserverService,
    ) -> None:
        """Initialize observed OCR service.

        Args:
            inner: Underlying OCR service implementation
            observer: Weave observer service for tracking
        """
        self._inner = inner
        self._observer = observer

    async def extract_text(
        self,
        image_bytes: bytes,
        source: LectureVisualSource,
        session_id: str = "",
        timestamp_ms: int = 0,
    ) -> VisionOCRResult:
        """Extract OCR text with observation tracking.

        Args:
            image_bytes: Raw image bytes
            source: Visual source type (slide/board)
            session_id: Lecture session ID for tracking
            timestamp_ms: Event timestamp for tracking

        Returns:
            OCR result with text and confidence
        """
        # Call inner service
        result = await self._inner.extract_text(image_bytes, source)

        # Determine quality from confidence
        quality = _classify_quality(result.confidence)

        # Track with image (NON-BLOCKING via dispatcher)
        # Determine source from inner service class name
        source_type = (
            "azure-vision"
            if self._inner.__class__.__name__ == "AzureVisionOCRService"
            else "ocr"
        )
        await self._observer.track_ocr_with_image(
            session_id=session_id,
            timestamp_ms=timestamp_ms,
            source=source_type,
            ocr_text=result.text,
            ocr_confidence=result.confidence,
            quality=quality,
            change_score=0.0,
            image_bytes=image_bytes,
        )

        return result


def _classify_quality(confidence: float) -> str:
    """Map OCR confidence to quality bands."""
    if confidence >= 0.8:
        return "good"
    if confidence >= 0.5:
        return "warn"
    return "bad"

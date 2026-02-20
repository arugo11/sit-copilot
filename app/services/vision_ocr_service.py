"""OCR adapter interfaces for lecture visual event ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.lecture import LectureVisualSource

__all__ = [
    "NoopVisionOCRService",
    "VisionOCRResult",
    "VisionOCRServiceError",
    "VisionOCRService",
]


@dataclass(frozen=True)
class VisionOCRResult:
    """OCR extraction result."""

    text: str
    confidence: float


class VisionOCRServiceError(Exception):
    """Raised when OCR provider processing fails."""


class VisionOCRService(Protocol):
    """Protocol for OCR providers."""

    async def extract_text(
        self,
        image_bytes: bytes,
        source: LectureVisualSource,
    ) -> VisionOCRResult:
        """Extract text and confidence from an image."""
        ...


class NoopVisionOCRService:
    """Deterministic fallback OCR provider used by default."""

    async def extract_text(
        self,
        image_bytes: bytes,
        source: LectureVisualSource,
    ) -> VisionOCRResult:
        """Return an empty OCR result for safe local development."""
        del image_bytes, source
        return VisionOCRResult(text="", confidence=0.0)

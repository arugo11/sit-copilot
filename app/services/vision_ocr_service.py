"""OCR adapter interfaces for lecture visual event ingestion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from app.schemas.lecture import LectureVisualSource

__all__ = [
    "AzureVisionOCRService",
    "NoopVisionOCRService",
    "VisionOCRLine",
    "VisionOCRResult",
    "VisionOCRServiceError",
    "VisionOCRService",
]


@dataclass(frozen=True)
class VisionOCRResult:
    """OCR extraction result."""

    text: str
    confidence: float


@dataclass(frozen=True)
class VisionOCRLine:
    """OCR line unit with per-line confidence."""

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


class VisionOCRAnalyzer(Protocol):
    """Protocol for provider-specific OCR extraction implementation."""

    def __call__(
        self,
        *,
        endpoint: str,
        api_key: str,
        image_bytes: bytes,
    ) -> list[VisionOCRLine]:
        """Analyze an image and return OCR lines with confidences."""
        ...


SLIDE_MIN_LINE_CONFIDENCE = 0.75
BOARD_MIN_LINE_CONFIDENCE = 0.68


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


class AzureVisionOCRService:
    """Azure AI Vision OCR provider."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        analyzer: VisionOCRAnalyzer | None = None,
    ) -> None:
        self._endpoint = _normalize_vision_endpoint(endpoint)
        self._api_key = api_key.strip()
        self._analyzer = analyzer or analyze_image_with_azure_vision

    async def extract_text(
        self,
        image_bytes: bytes,
        source: LectureVisualSource,
    ) -> VisionOCRResult:
        """Extract OCR text from image bytes using Azure AI Vision."""
        if not self._endpoint or not self._api_key:
            raise VisionOCRServiceError("Vision OCR service is not configured.")

        try:
            lines = await asyncio.to_thread(
                self._analyzer,
                endpoint=self._endpoint,
                api_key=self._api_key,
                image_bytes=image_bytes,
            )
        except VisionOCRServiceError:
            raise
        except Exception as exc:
            raise VisionOCRServiceError("Vision OCR provider request failed.") from exc

        threshold = _line_confidence_threshold(source)
        retained_lines = [line for line in lines if line.confidence >= threshold]
        if not retained_lines:
            return VisionOCRResult(text="", confidence=0.0)

        text = "\n".join(line.text for line in retained_lines)
        confidence = sum(line.confidence for line in retained_lines) / len(retained_lines)
        return VisionOCRResult(
            text=text.strip(),
            confidence=_clamp_confidence(confidence),
        )


def analyze_image_with_azure_vision(
    *,
    endpoint: str,
    api_key: str,
    image_bytes: bytes,
) -> list[VisionOCRLine]:
    """Run Azure AI Vision READ analysis and extract OCR lines."""
    try:
        from azure.ai.vision.imageanalysis import ImageAnalysisClient
        from azure.ai.vision.imageanalysis.models import VisualFeatures
        from azure.core.credentials import AzureKeyCredential
    except ModuleNotFoundError as exc:
        raise VisionOCRServiceError(
            "Azure Vision SDK is not installed in the current environment."
        ) from exc

    try:
        client = ImageAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
        )
        result = client.analyze(
            image_data=image_bytes,
            visual_features=[VisualFeatures.READ],
        )
    except Exception as exc:
        raise VisionOCRServiceError("Vision OCR provider request failed.") from exc

    return _extract_lines_from_analysis_result(result)


def _extract_lines_from_analysis_result(result: object) -> list[VisionOCRLine]:
    """Extract OCR lines from Azure image analysis result object."""
    read_result = getattr(result, "read", None)
    blocks = getattr(read_result, "blocks", None) if read_result is not None else None
    if not blocks:
        return []

    lines: list[VisionOCRLine] = []
    for block in blocks:
        block_lines = getattr(block, "lines", None)
        if not block_lines:
            continue

        for line in block_lines:
            text = str(getattr(line, "text", "")).strip()
            if not text:
                continue
            confidence = _resolve_line_confidence(line)
            lines.append(VisionOCRLine(text=text, confidence=confidence))

    return lines


def _resolve_line_confidence(line: object) -> float:
    """Resolve confidence for one OCR line from line/word properties."""
    raw_line_confidence = getattr(line, "confidence", None)
    if isinstance(raw_line_confidence, int | float):
        return _clamp_confidence(float(raw_line_confidence))

    words = getattr(line, "words", None)
    if not words:
        return 0.0

    confidences: list[float] = []
    for word in words:
        raw_confidence = getattr(word, "confidence", None)
        if isinstance(raw_confidence, int | float):
            confidences.append(_clamp_confidence(float(raw_confidence)))

    if not confidences:
        return 0.0

    return _clamp_confidence(sum(confidences) / len(confidences))


def _line_confidence_threshold(source: LectureVisualSource) -> float:
    """Return source-specific minimum line confidence threshold."""
    if source == "slide":
        return SLIDE_MIN_LINE_CONFIDENCE
    return BOARD_MIN_LINE_CONFIDENCE


def _normalize_vision_endpoint(endpoint: str) -> str:
    """Normalize Azure Vision endpoint to canonical URL format."""
    normalized_endpoint = endpoint.strip().rstrip("/")
    if not normalized_endpoint:
        return ""

    parsed = urlparse(normalized_endpoint)
    host = parsed.netloc.lower()
    if not host:
        return normalized_endpoint

    if host.endswith(".api.cognitive.microsoft.com"):
        return normalized_endpoint

    if host.endswith(".cognitiveservices.azure.com"):
        return normalized_endpoint

    return normalized_endpoint


def _clamp_confidence(confidence: float) -> float:
    """Clamp confidence to [0.0, 1.0]."""
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return confidence

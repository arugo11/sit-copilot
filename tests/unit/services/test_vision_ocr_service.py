"""Unit tests for Azure Vision OCR service."""

import pytest

from app.services.vision_ocr_service import (
    AzureVisionOCRService,
    VisionOCRLine,
    VisionOCRServiceError,
)


def _successful_analyzer(
    *,
    endpoint: str,
    api_key: str,
    image_bytes: bytes,
) -> list[VisionOCRLine]:
    _ = (endpoint, api_key, image_bytes)
    return [
        VisionOCRLine(text="外れ値", confidence=0.92),
        VisionOCRLine(text="残差確認", confidence=0.70),
    ]


@pytest.mark.asyncio
async def test_extract_text_raises_when_service_is_not_configured() -> None:
    """Service should reject extraction when endpoint/key are missing."""
    service = AzureVisionOCRService(
        endpoint="",
        api_key="",
        analyzer=_successful_analyzer,
    )

    with pytest.raises(VisionOCRServiceError):
        await service.extract_text(image_bytes=b"jpeg", source="slide")


@pytest.mark.asyncio
async def test_extract_text_filters_lines_by_slide_threshold() -> None:
    """Slide source should filter out lines below 0.75 confidence."""
    service = AzureVisionOCRService(
        endpoint="https://japaneast.api.cognitive.microsoft.com",
        api_key="dummy-key",
        analyzer=_successful_analyzer,
    )

    response = await service.extract_text(image_bytes=b"jpeg", source="slide")

    assert response.text == "外れ値"
    assert response.confidence == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_extract_text_allows_board_threshold_lines() -> None:
    """Board source should keep lines above 0.68 confidence."""
    service = AzureVisionOCRService(
        endpoint="https://japaneast.api.cognitive.microsoft.com",
        api_key="dummy-key",
        analyzer=_successful_analyzer,
    )

    response = await service.extract_text(image_bytes=b"jpeg", source="board")

    assert response.text == "外れ値\n残差確認"
    assert response.confidence == pytest.approx((0.92 + 0.70) / 2)


@pytest.mark.asyncio
async def test_extract_text_returns_empty_when_no_lines_meet_threshold() -> None:
    """Service should return empty low-confidence result when all lines are filtered."""

    def low_confidence_analyzer(
        *,
        endpoint: str,
        api_key: str,
        image_bytes: bytes,
    ) -> list[VisionOCRLine]:
        _ = (endpoint, api_key, image_bytes)
        return [VisionOCRLine(text="判読不可", confidence=0.40)]

    service = AzureVisionOCRService(
        endpoint="https://japaneast.api.cognitive.microsoft.com",
        api_key="dummy-key",
        analyzer=low_confidence_analyzer,
    )

    response = await service.extract_text(image_bytes=b"jpeg", source="slide")

    assert response.text == ""
    assert response.confidence == 0.0


@pytest.mark.asyncio
async def test_extract_text_maps_analyzer_failure_to_service_error() -> None:
    """Unexpected analyzer errors should be converted to service errors."""

    def failing_analyzer(
        *,
        endpoint: str,
        api_key: str,
        image_bytes: bytes,
    ) -> list[VisionOCRLine]:
        _ = (endpoint, api_key, image_bytes)
        raise RuntimeError("provider failed")

    service = AzureVisionOCRService(
        endpoint="https://japaneast.api.cognitive.microsoft.com",
        api_key="dummy-key",
        analyzer=failing_analyzer,
    )

    with pytest.raises(VisionOCRServiceError):
        await service.extract_text(image_bytes=b"jpeg", source="slide")

"""Unit tests for live caption transform service."""

import pytest
from unittest.mock import AsyncMock

from app.core.azure_openai_config import ValidationResult
from app.services.live_caption_transform_service import (
    AzureOpenAILiveCaptionTransformService,
)


@pytest.mark.asyncio
async def test_transform_easy_ja_uses_local_fallback_when_azure_unavailable() -> None:
    service = AzureOpenAILiveCaptionTransformService(
        api_key="",
        endpoint="",
        model="gpt-4o",
    )

    transformed = await service.transform(
        "機械学習は未知データで性能を確認します。",
        "easy-ja",
    )

    assert "AIの学習" in transformed
    assert "はじめてのデータ" in transformed


@pytest.mark.asyncio
async def test_transform_en_uses_local_fallback_when_azure_unavailable() -> None:
    service = AzureOpenAILiveCaptionTransformService(
        api_key="",
        endpoint="",
        model="gpt-4o",
    )

    transformed = await service.transform(
        "検証データで過学習を確認します。",
        "en",
    )

    assert "validation data" in transformed
    assert "overfitting" in transformed


@pytest.mark.asyncio
async def test_transform_en_uses_llm_when_configuration_is_valid() -> None:
    service = AzureOpenAILiveCaptionTransformService(
        api_key="dummy",
        endpoint="https://example.openai.azure.com",
        model="gpt-4o",
    )
    service._validation = ValidationResult(  # type: ignore[assignment]
        is_valid=True,
        normalized_endpoint="https://example.openai.azure.com",
        reason="ok",
    )
    service._call_openai = AsyncMock(return_value="Machine learning verifies performance with unseen data.")  # type: ignore[method-assign]

    transformed = await service.transform(
        "機械学習は未知データで性能を確認します。",
        "en",
    )

    assert transformed == "Machine learning verifies performance with unseen data."
    service._call_openai.assert_awaited_once()

"""Unit tests for live caption transform service."""

from unittest.mock import AsyncMock

import pytest

from app.core.azure_openai_config import ValidationResult
from app.services.live_caption_transform_service import (
    AzureOpenAILiveCaptionTransformService,
    CaptionTransformLLMError,
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

    assert transformed.status == "fallback"
    assert transformed.fallback_reason == "missing_api_key"
    assert "AIの学習" in transformed.text
    assert "はじめてのデータ" in transformed.text


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

    assert transformed.status == "fallback"
    assert transformed.fallback_reason == "missing_api_key"
    assert "validation data" in transformed.text
    assert "overfitting" in transformed.text


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

    assert transformed.status == "translated"
    assert transformed.fallback_reason is None
    assert transformed.text == "Machine learning verifies performance with unseen data."
    service._call_openai.assert_awaited_once()


@pytest.mark.asyncio
async def test_transform_ja_returns_passthrough_status() -> None:
    service = AzureOpenAILiveCaptionTransformService(
        api_key="dummy",
        endpoint="https://example.openai.azure.com",
        model="gpt-5-nano",
    )

    transformed = await service.transform("この式は分散の定義です。", "ja")

    assert transformed.status == "passthrough"
    assert transformed.fallback_reason is None
    assert transformed.text == "この式は分散の定義です。"


@pytest.mark.asyncio
async def test_transform_en_empty_llm_output_returns_fallback_result() -> None:
    service = AzureOpenAILiveCaptionTransformService(
        api_key="dummy",
        endpoint="https://example.openai.azure.com",
        model="gpt-5-nano",
    )
    service._validation = ValidationResult(  # type: ignore[assignment]
        is_valid=True,
        normalized_endpoint="https://example.openai.azure.com",
        reason="ok",
    )
    service._call_openai = AsyncMock(return_value="   ")  # type: ignore[method-assign]

    transformed = await service.transform(
        "機械学習は未知データで性能を確認します。",
        "en",
    )

    assert transformed.status == "fallback"
    assert transformed.fallback_reason == "llm_empty_response"
    assert "machine learning" in transformed.text
    service._call_openai.assert_awaited_once()


def test_build_chat_completion_payload_adds_reasoning_effort_for_gpt5() -> None:
    service = AzureOpenAILiveCaptionTransformService(
        api_key="dummy",
        endpoint="https://example.openai.azure.com",
        model="gpt-5-nano",
    )
    prompt = service._build_en_prompt("機械学習は未知データで性能を確認します。")

    payload = service._build_chat_completion_payload(prompt)

    assert payload["reasoning_effort"] == "minimal"


@pytest.mark.asyncio
async def test_transform_retries_rate_limit_error_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AzureOpenAILiveCaptionTransformService(
        api_key="dummy",
        endpoint="https://example.openai.azure.com",
        model="gpt-5-nano",
    )
    service._validation = ValidationResult(  # type: ignore[assignment]
        is_valid=True,
        normalized_endpoint="https://example.openai.azure.com",
        reason="ok",
    )
    sleep_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.live_caption_transform_service.asyncio.sleep",
        sleep_mock,
    )
    service._call_openai = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            CaptionTransformLLMError(
                reason="llm_rate_limited",
                message="rate limit",
                retry_after_seconds=0.1,
            ),
            "translated output",
        ]
    )

    transformed = await service.transform("機械学習は未知データで性能を確認します。", "en")

    assert transformed.status == "translated"
    assert transformed.text == "translated output"
    assert transformed.fallback_reason is None
    service._call_openai.assert_awaited()
    assert service._call_openai.await_count == 2
    sleep_mock.assert_awaited_once_with(0.1)


@pytest.mark.asyncio
async def test_transform_does_not_retry_non_retriable_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AzureOpenAILiveCaptionTransformService(
        api_key="dummy",
        endpoint="https://example.openai.azure.com",
        model="gpt-5-nano",
    )
    service._validation = ValidationResult(  # type: ignore[assignment]
        is_valid=True,
        normalized_endpoint="https://example.openai.azure.com",
        reason="ok",
    )
    sleep_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.live_caption_transform_service.asyncio.sleep",
        sleep_mock,
    )
    service._call_openai = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            CaptionTransformLLMError(
                reason="llm_parse_error",
                message="parse failed",
            )
        ]
    )

    transformed = await service.transform("検証データで過学習を確認します。", "en")

    assert transformed.status == "fallback"
    assert transformed.fallback_reason == "llm_parse_error"
    assert "validation data" in transformed.text
    assert service._call_openai.await_count == 1
    sleep_mock.assert_not_awaited()

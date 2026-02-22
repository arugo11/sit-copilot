"""Unit tests for Japanese ASR correction service."""

import logging
from unittest.mock import AsyncMock

import pytest

from app.core.azure_openai_config import ValidationResult
from app.services.asr_japanese_correction_service import (
    AzureOpenAIJapaneseASRCorrectionService,
    NoopJapaneseASRCorrectionService,
)


@pytest.mark.asyncio
async def test_correct_minimally_runs_second_pass_when_unchanged() -> None:
    service = AzureOpenAIJapaneseASRCorrectionService(
        api_key="dummy",
        endpoint="https://example.openai.azure.com",
        model="gpt-4o",
    )
    service._validation = ValidationResult(  # type: ignore[assignment]
        is_valid=True,
        normalized_endpoint="https://example.openai.azure.com",
        reason="ok",
    )
    source_text = (
        "天候が不安定なので折りたたみ傘を持って出かけるべき"
        "主流とされているのは駅前の商店街と同様"
    )
    service._call_openai = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            source_text,
            "天候が不安定なので折りたたみ傘を持って出かけるべき"
            "主流とされているのは駅前のアーケード商店街と同様",
        ]
    )

    corrected = await service.correct_minimally(source_text)

    assert "折りたたみ傘" in corrected
    assert "アーケード商店街" in corrected
    assert service._call_openai.await_count == 2


@pytest.mark.asyncio
async def test_correct_minimally_skips_second_pass_for_short_text() -> None:
    service = AzureOpenAIJapaneseASRCorrectionService(
        api_key="dummy",
        endpoint="https://example.openai.azure.com",
        model="gpt-4o",
    )
    service._validation = ValidationResult(  # type: ignore[assignment]
        is_valid=True,
        normalized_endpoint="https://example.openai.azure.com",
        reason="ok",
    )
    service._call_openai = AsyncMock(return_value="短文")  # type: ignore[method-assign]

    corrected = await service.correct_minimally("短文")

    assert corrected == "短文"
    service._call_openai.assert_awaited_once()


@pytest.mark.asyncio
async def test_noop_correction_emits_warning_only_once(caplog: pytest.LogCaptureFixture) -> None:
    NoopJapaneseASRCorrectionService._warning_emitted = False
    service = NoopJapaneseASRCorrectionService(
        warning_reason="azure_openai_disabled_request_fallback env=AZURE_OPENAI_ENABLED|AZURE_OPENAI_ENABLE endpoint=/api/v4/lecture/subtitle/audit using=noop_correction"
    )

    with caplog.at_level(logging.WARNING):
        first = await service.correct_minimally("  補正前  ")
        second = await service.correct_minimally("  補正前  ")

    assert first == "補正前"
    assert second == "補正前"
    warning_records = [
        record
        for record in caplog.records
        if "azure_openai_disabled_request_fallback" in record.getMessage()
    ]
    assert len(warning_records) == 1

"""Unit tests for speech token service."""

import pytest

from app.services.speech_token_service import (
    AzureSpeechTokenService,
    SpeechTokenConfigurationError,
    SpeechTokenProviderError,
)


@pytest.mark.asyncio
async def test_issue_token_raises_configuration_error_when_key_missing() -> None:
    """Service should reject issuance when speech key is not configured."""
    service = AzureSpeechTokenService(
        speech_key="",
        speech_region="japaneast",
    )

    with pytest.raises(SpeechTokenConfigurationError):
        await service.issue_token()


@pytest.mark.asyncio
async def test_issue_token_raises_provider_error_when_request_fails() -> None:
    """Service should map requester failure to provider error."""

    def failing_requester(
        *, sts_endpoint: str, speech_key: str, timeout_seconds: int
    ) -> str:
        _ = (sts_endpoint, speech_key, timeout_seconds)
        raise RuntimeError("sts request failed")

    service = AzureSpeechTokenService(
        speech_key="dummy-key",
        speech_region="japaneast",
        requester=failing_requester,
    )

    with pytest.raises(SpeechTokenProviderError):
        await service.issue_token()


@pytest.mark.asyncio
async def test_issue_token_returns_contract_values_on_success() -> None:
    """Service should return token payload with region and conservative expiry."""
    captured: dict[str, object] = {}

    def successful_requester(
        *,
        sts_endpoint: str,
        speech_key: str,
        timeout_seconds: int,
    ) -> str:
        captured["sts_endpoint"] = sts_endpoint
        captured["speech_key"] = speech_key
        captured["timeout_seconds"] = timeout_seconds
        return "issued-token"

    service = AzureSpeechTokenService(
        speech_key="dummy-key",
        speech_region="japaneast",
        requester=successful_requester,
    )

    response = await service.issue_token()

    assert response.token == "issued-token"
    assert response.region == "japaneast"
    assert response.expires_in_sec == 540
    assert captured["sts_endpoint"] == (
        "https://japaneast.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    )
    assert captured["speech_key"] == "dummy-key"
    assert captured["timeout_seconds"] == 5


@pytest.mark.asyncio
async def test_issue_token_raises_provider_error_when_token_is_empty() -> None:
    """Service should reject empty token responses from provider."""

    def empty_token_requester(
        *,
        sts_endpoint: str,
        speech_key: str,
        timeout_seconds: int,
    ) -> str:
        _ = (sts_endpoint, speech_key, timeout_seconds)
        return ""

    service = AzureSpeechTokenService(
        speech_key="dummy-key",
        speech_region="japaneast",
        requester=empty_token_requester,
    )

    with pytest.raises(SpeechTokenProviderError):
        await service.issue_token()

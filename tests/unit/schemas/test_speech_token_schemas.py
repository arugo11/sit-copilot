"""Unit tests for speech token schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.speech_token import SpeechTokenResponse


def test_speech_token_response_accepts_valid_payload() -> None:
    """SpeechTokenResponse should accept a valid contract payload."""
    payload = {
        "token": "speech-token-value",
        "region": "japaneast",
        "expires_in_sec": 540,
    }

    response = SpeechTokenResponse.model_validate(payload)

    assert response.token == payload["token"]
    assert response.region == payload["region"]
    assert response.expires_in_sec == payload["expires_in_sec"]


def test_speech_token_response_rejects_blank_token() -> None:
    """SpeechTokenResponse should reject blank token values."""
    payload = {
        "token": "   ",
        "region": "japaneast",
        "expires_in_sec": 540,
    }

    with pytest.raises(ValidationError):
        SpeechTokenResponse.model_validate(payload)


def test_speech_token_response_rejects_blank_region() -> None:
    """SpeechTokenResponse should reject blank region values."""
    payload = {
        "token": "speech-token-value",
        "region": "   ",
        "expires_in_sec": 540,
    }

    with pytest.raises(ValidationError):
        SpeechTokenResponse.model_validate(payload)


def test_speech_token_response_rejects_non_positive_expiry() -> None:
    """SpeechTokenResponse should reject non-positive expiry values."""
    payload = {
        "token": "speech-token-value",
        "region": "japaneast",
        "expires_in_sec": 0,
    }

    with pytest.raises(ValidationError):
        SpeechTokenResponse.model_validate(payload)

"""Unit tests for application settings validation."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_normalizes_azure_speech_region() -> None:
    """Settings should normalize speech region to lowercase."""
    configured = Settings(_env_file=None, azure_speech_region="JapanEast")

    assert configured.azure_speech_region == "japaneast"


def test_settings_rejects_invalid_azure_speech_region_format() -> None:
    """Settings should reject speech region with unsupported characters."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, azure_speech_region="japan east!")


def test_settings_rejects_invalid_speech_token_expiry() -> None:
    """Settings should reject out-of-range speech token expiry values."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, azure_speech_token_expires_in_sec=601)


def test_settings_rejects_invalid_speech_timeout() -> None:
    """Settings should reject non-positive speech STS timeout values."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, azure_speech_sts_timeout_seconds=0)

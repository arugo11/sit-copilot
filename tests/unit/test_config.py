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


def test_settings_accepts_azure_vision_configuration_fields() -> None:
    """Settings should include Azure Vision configuration values."""
    configured = Settings(
        _env_file=None,
        azure_vision_enabled=True,
        azure_vision_key="dummy-vision-key",
        azure_vision_endpoint="https://japaneast.api.cognitive.microsoft.com/",
    )

    assert configured.azure_vision_enabled is True
    assert configured.azure_vision_key == "dummy-vision-key"
    assert configured.azure_vision_endpoint == (
        "https://japaneast.api.cognitive.microsoft.com/"
    )


def test_settings_accepts_legacy_azure_openai_enable_env_alias() -> None:
    """Settings should accept AZURE_OPENAI_ENABLE as alias."""
    configured = Settings(
        _env_file=None,
        AZURE_OPENAI_ENABLE="true",
    )

    assert configured.azure_openai_enabled is True


def test_settings_default_model_stack_matches_demo_baseline() -> None:
    """Settings should expose the intended default LLM/ASR/TTS baseline."""
    configured = Settings(_env_file=None)

    assert configured.azure_openai_model == "gpt-5-mini"
    assert configured.lecture_qa_verifier_model == "gpt-5-nano"
    assert configured.lecture_qa_repair_model == "gpt-5-mini"
    assert configured.azure_openai_keyterms_model == "gpt-5-nano"
    assert configured.azure_openai_judge_model == "gpt-5-nano"
    assert configured.azure_speech_recognition_locale == "ja-JP"
    assert configured.azure_speech_tts_voice == "ja-JP-NanamiNeural"

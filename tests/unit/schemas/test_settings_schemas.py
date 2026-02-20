"""Unit tests for settings schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.settings import SettingsResponse, SettingsUpsertRequest


def test_settings_upsert_request_accepts_valid_dict() -> None:
    """SettingsUpsertRequest should accept a valid dictionary payload."""
    # Arrange
    payload = {
        "settings": {
            "theme": "dark",
            "notifications_enabled": True,
        }
    }

    # Act
    request = SettingsUpsertRequest.model_validate(payload)

    # Assert
    assert request.settings["theme"] == "dark"
    assert request.settings["notifications_enabled"] is True


def test_settings_upsert_request_rejects_non_dict() -> None:
    """SettingsUpsertRequest should reject non-dict settings payload."""
    # Arrange
    payload = {"settings": ["invalid", "list"]}

    # Act / Assert
    with pytest.raises(ValidationError):
        SettingsUpsertRequest.model_validate(payload)


def test_settings_upsert_request_rejects_extra_fields() -> None:
    """SettingsUpsertRequest should reject unknown top-level fields."""
    # Arrange
    payload = {
        "settings": {"theme": "dark"},
        "unexpected": "value",
    }

    # Act / Assert
    with pytest.raises(ValidationError):
        SettingsUpsertRequest.model_validate(payload)


def test_settings_response_serializes_expected_fields() -> None:
    """SettingsResponse should serialize user settings with timestamp."""
    # Arrange
    now = datetime.now(UTC)
    response = SettingsResponse(
        user_id="demo_user",
        settings={"theme": "light"},
        updated_at=now,
    )

    # Act
    dumped = response.model_dump(mode="json")

    # Assert
    assert dumped["user_id"] == "demo_user"
    assert dumped["settings"]["theme"] == "light"
    assert dumped["updated_at"] is not None

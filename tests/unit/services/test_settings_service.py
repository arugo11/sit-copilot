"""Unit tests for settings service."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.settings import SettingsUpsertRequest
from app.services.settings_service import SqlAlchemySettingsService


@pytest.mark.asyncio
async def test_get_my_settings_returns_empty_dict_when_not_found(
    db_session: AsyncSession,
) -> None:
    """Service should return empty settings for unknown user."""
    # Arrange
    service = SqlAlchemySettingsService(db_session)

    # Act
    response = await service.get_my_settings("unknown_user")

    # Assert
    assert response.user_id == "unknown_user"
    assert response.settings == {}
    assert response.updated_at is None


@pytest.mark.asyncio
async def test_upsert_my_settings_creates_user_and_settings(
    db_session: AsyncSession,
) -> None:
    """Service should create both user and user settings on first upsert."""
    # Arrange
    service = SqlAlchemySettingsService(db_session)
    request = SettingsUpsertRequest(settings={"theme": "dark"})

    # Act
    response = await service.upsert_my_settings("demo_user", request)

    # Assert
    assert response.user_id == "demo_user"
    assert response.settings == {"theme": "dark"}
    assert response.updated_at is not None

    user_result = await db_session.execute(select(User).where(User.id == "demo_user"))
    user = user_result.scalar_one_or_none()
    assert user is not None

    settings_result = await db_session.execute(
        select(UserSettings).where(UserSettings.user_id == "demo_user")
    )
    user_settings = settings_result.scalar_one_or_none()
    assert user_settings is not None
    assert user_settings.settings == {"theme": "dark"}


@pytest.mark.asyncio
async def test_upsert_my_settings_updates_existing_record(
    db_session: AsyncSession,
) -> None:
    """Service should update existing settings and refresh updated_at."""
    # Arrange
    service = SqlAlchemySettingsService(db_session)
    first_request = SettingsUpsertRequest(settings={"theme": "dark"})
    second_request = SettingsUpsertRequest(
        settings={"theme": "light", "notifications_enabled": True}
    )

    # Act
    first_response = await service.upsert_my_settings("demo_user", first_request)
    second_response = await service.upsert_my_settings("demo_user", second_request)

    # Assert
    assert first_response.settings == {"theme": "dark"}
    assert second_response.settings == {
        "theme": "light",
        "notifications_enabled": True,
    }
    assert first_response.updated_at is not None
    assert second_response.updated_at is not None
    assert second_response.updated_at >= first_response.updated_at

    result = await db_session.execute(
        select(UserSettings).where(UserSettings.user_id == "demo_user")
    )
    persisted = result.scalar_one_or_none()
    assert persisted is not None
    assert persisted.settings == {
        "theme": "light",
        "notifications_enabled": True,
    }

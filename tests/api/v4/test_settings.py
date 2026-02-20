"""Integration tests for settings API endpoints."""

import pytest
from httpx import AsyncClient

from app.core.auth import LECTURE_TOKEN_HEADER, USER_ID_HEADER
from app.core.config import settings

AUTH_HEADERS = {
    LECTURE_TOKEN_HEADER: settings.lecture_api_token,
    USER_ID_HEADER: "settings_test_user",
}


@pytest.mark.asyncio
async def test_get_settings_returns_200_with_empty_defaults(
    async_client: AsyncClient,
) -> None:
    """GET should return empty settings when no record exists yet."""
    # Act
    response = await async_client.get("/api/v4/settings/me", headers=AUTH_HEADERS)

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "user_id": "settings_test_user",
        "settings": {},
        "updated_at": None,
    }


@pytest.mark.asyncio
async def test_post_settings_creates_settings(async_client: AsyncClient) -> None:
    """POST should create settings for the authenticated user."""
    # Arrange
    payload = {
        "settings": {
            "theme": "dark",
            "notifications_enabled": True,
        }
    }

    # Act
    response = await async_client.post(
        "/api/v4/settings/me",
        json=payload,
        headers=AUTH_HEADERS,
    )
    body = response.json()

    # Assert
    assert response.status_code == 200
    assert body["user_id"] == "settings_test_user"
    assert body["settings"] == payload["settings"]
    assert body["updated_at"] is not None


@pytest.mark.asyncio
async def test_post_then_get_returns_updated_settings(async_client: AsyncClient) -> None:
    """GET should return latest settings after POST update."""
    # Arrange
    payload = {"settings": {"theme": "light", "font_size": "large"}}

    # Act
    post_response = await async_client.post(
        "/api/v4/settings/me",
        json=payload,
        headers=AUTH_HEADERS,
    )
    get_response = await async_client.get("/api/v4/settings/me", headers=AUTH_HEADERS)

    # Assert
    assert post_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["settings"] == payload["settings"]


@pytest.mark.asyncio
async def test_post_settings_with_invalid_payload_returns_400(
    async_client: AsyncClient,
) -> None:
    """Validation failures should return common 400 error response."""
    # Arrange
    invalid_payload = {"settings": ["not", "a", "dict"]}

    # Act
    response = await async_client.post(
        "/api/v4/settings/me",
        json=invalid_payload,
        headers=AUTH_HEADERS,
    )
    body = response.json()

    # Assert
    assert response.status_code == 400
    assert "error" in body
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Invalid request parameters."
    assert isinstance(body["error"]["details"], list)


@pytest.mark.asyncio
async def test_get_settings_without_auth_returns_401(
    async_client: AsyncClient,
) -> None:
    """Settings endpoint should reject requests without auth headers."""
    response = await async_client.get("/api/v4/settings/me")

    assert response.status_code == 401

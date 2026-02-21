"""Integration tests for auth API endpoints."""

import pytest
from httpx import AsyncClient

from app.api.v4 import auth as auth_api
from app.core.auth import LECTURE_TOKEN_HEADER
from app.core.config import settings
from app.main import app
from app.services import speech_token_service as speech_token_service_module
from app.services.speech_token_service import SpeechTokenProviderError

AUTH_HEADERS = {LECTURE_TOKEN_HEADER: settings.lecture_api_token}


class _SuccessSpeechTokenService:
    async def issue_token(self) -> dict[str, object]:
        return {
            "token": "issued-token",
            "region": "japaneast",
            "expires_in_sec": 540,
        }


class _FailureSpeechTokenService:
    async def issue_token(self) -> dict[str, object]:
        raise SpeechTokenProviderError("provider failure")


class _AlwaysBlockedRateLimiter:
    async def allow(self, key: str) -> bool:
        _ = key
        return False


@pytest.mark.asyncio
async def test_get_speech_token_returns_200(async_client: AsyncClient) -> None:
    """Speech token endpoint should return token payload on success."""
    app.dependency_overrides[auth_api.get_speech_token_service] = lambda: (
        _SuccessSpeechTokenService()
    )

    try:
        response = await async_client.get(
            "/api/v4/auth/speech-token",
            headers=AUTH_HEADERS,
        )
        body = response.json()
    finally:
        app.dependency_overrides.pop(auth_api.get_speech_token_service, None)

    assert response.status_code == 200
    assert body == {
        "token": "issued-token",
        "region": "japaneast",
        "expires_in_sec": 540,
    }


@pytest.mark.asyncio
async def test_get_speech_token_without_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Speech token endpoint should reject unauthenticated requests."""
    response = await async_client.get("/api/v4/auth/speech-token")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_speech_token_returns_503_on_provider_failure(
    async_client: AsyncClient,
) -> None:
    """Speech token endpoint should map provider failures to 503."""
    app.dependency_overrides[auth_api.get_speech_token_service] = lambda: (
        _FailureSpeechTokenService()
    )

    try:
        response = await async_client.get(
            "/api/v4/auth/speech-token",
            headers=AUTH_HEADERS,
        )
        body = response.json()
    finally:
        app.dependency_overrides.pop(auth_api.get_speech_token_service, None)

    assert response.status_code == 503
    assert body["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_get_speech_token_returns_429_when_rate_limited(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Speech token endpoint should reject requests over rate limit."""
    app.dependency_overrides[auth_api.get_speech_token_service] = lambda: (
        _SuccessSpeechTokenService()
    )
    monkeypatch.setattr(
        auth_api,
        "_speech_token_rate_limiter",
        _AlwaysBlockedRateLimiter(),
    )

    try:
        response = await async_client.get(
            "/api/v4/auth/speech-token",
            headers=AUTH_HEADERS,
        )
        body = response.json()
    finally:
        app.dependency_overrides.pop(auth_api.get_speech_token_service, None)

    assert response.status_code == 429
    assert body["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_get_speech_token_uses_real_factory_with_settings(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Speech token endpoint should work through default DI factory path."""
    captured: dict[str, object] = {}

    def fake_issue_speech_token_via_sts(
        *,
        sts_endpoint: str,
        speech_key: str,
        timeout_seconds: int,
    ) -> str:
        captured["sts_endpoint"] = sts_endpoint
        captured["speech_key"] = speech_key
        captured["timeout_seconds"] = timeout_seconds
        return "factory-token"

    monkeypatch.setattr(settings, "azure_speech_key", "factory-key")
    monkeypatch.setattr(settings, "azure_speech_region", "japaneast")
    monkeypatch.setattr(settings, "azure_speech_token_expires_in_sec", 530)
    monkeypatch.setattr(settings, "azure_speech_sts_timeout_seconds", 7)
    monkeypatch.setattr(
        speech_token_service_module,
        "issue_speech_token_via_sts",
        fake_issue_speech_token_via_sts,
    )

    response = await async_client.get(
        "/api/v4/auth/speech-token",
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body == {
        "token": "factory-token",
        "region": "japaneast",
        "expires_in_sec": 530,
    }
    assert captured["sts_endpoint"] == (
        "https://japaneast.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    )
    assert captured["speech_key"] == "factory-key"
    assert captured["timeout_seconds"] == 7

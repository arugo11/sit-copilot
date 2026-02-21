"""Azure Speech token issuance service."""

from __future__ import annotations

import asyncio
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.schemas.speech_token import SpeechTokenResponse

DEFAULT_TOKEN_EXPIRES_IN_SEC = 540
DEFAULT_STS_TIMEOUT_SECONDS = 5


class SpeechTokenRequester(Protocol):
    """Protocol for STS requester call signature."""

    def __call__(
        self,
        *,
        sts_endpoint: str,
        speech_key: str,
        timeout_seconds: int,
    ) -> str:
        """Request speech token from STS endpoint."""
        ...


class SpeechTokenConfigurationError(Exception):
    """Raised when speech token service is not configured."""


class SpeechTokenProviderError(Exception):
    """Raised when Azure Speech STS request fails."""


class SpeechTokenService(Protocol):
    """Interface for speech token issuance."""

    async def issue_token(self) -> SpeechTokenResponse:
        """Issue short-lived token for Azure Speech SDK."""
        ...


def issue_speech_token_via_sts(
    *,
    sts_endpoint: str,
    speech_key: str,
    timeout_seconds: int,
) -> str:
    """Issue Azure Speech token through STS endpoint."""
    request = Request(
        url=sts_endpoint,
        method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": speech_key,
            "Content-Length": "0",
        },
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            token = response.read().decode("utf-8").strip()
    except (HTTPError, URLError, OSError) as exc:
        raise SpeechTokenProviderError("Speech token provider request failed.") from exc

    if not token:
        raise SpeechTokenProviderError("Speech token provider returned empty token.")

    return token


class AzureSpeechTokenService:
    """Azure Speech STS implementation of speech token service."""

    def __init__(
        self,
        *,
        speech_key: str,
        speech_region: str,
        expires_in_sec: int = DEFAULT_TOKEN_EXPIRES_IN_SEC,
        timeout_seconds: int = DEFAULT_STS_TIMEOUT_SECONDS,
        requester: SpeechTokenRequester | None = None,
    ) -> None:
        self._speech_key = speech_key
        self._speech_region = speech_region
        self._expires_in_sec = expires_in_sec
        self._timeout_seconds = timeout_seconds
        self._requester = requester

    async def issue_token(self) -> SpeechTokenResponse:
        """Issue short-lived Azure Speech SDK token."""
        normalized_key = self._speech_key.strip()
        normalized_region = self._speech_region.strip()
        if not normalized_key or not normalized_region:
            raise SpeechTokenConfigurationError(
                "Speech token service is not configured."
            )

        requester = self._requester or issue_speech_token_via_sts
        sts_endpoint = _build_speech_sts_endpoint(normalized_region)

        try:
            token = await asyncio.to_thread(
                requester,
                sts_endpoint=sts_endpoint,
                speech_key=normalized_key,
                timeout_seconds=self._timeout_seconds,
            )
        except SpeechTokenProviderError:
            raise
        except Exception as exc:
            raise SpeechTokenProviderError(
                "Speech token provider request failed."
            ) from exc

        normalized_token = token.strip()
        if not normalized_token:
            raise SpeechTokenProviderError("Speech token provider returned empty token.")

        return SpeechTokenResponse(
            token=normalized_token,
            region=normalized_region,
            expires_in_sec=self._expires_in_sec,
        )


def _build_speech_sts_endpoint(region: str) -> str:
    normalized = region.strip()
    return f"https://{normalized}.api.cognitive.microsoft.com/sts/v1.0/issueToken"

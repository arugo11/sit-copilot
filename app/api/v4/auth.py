"""Auth-related API endpoints."""

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.auth import USER_ID_HEADER, require_lecture_token
from app.core.config import settings
from app.schemas.speech_token import SpeechTokenResponse
from app.services.speech_token_service import (
    AzureSpeechTokenService,
    SpeechTokenConfigurationError,
    SpeechTokenProviderError,
    SpeechTokenService,
)

MAX_SPEECH_TOKEN_REQUESTS_PER_MINUTE = 30
SPEECH_TOKEN_RATE_LIMIT_WINDOW_SECONDS = 60.0

logger = logging.getLogger(__name__)


class SpeechTokenRateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        """Return whether the key can proceed under current rate limits."""
        now = time.monotonic()
        threshold = now - self._window_seconds

        async with self._lock:
            queue = self._events[key]
            while queue and queue[0] < threshold:
                queue.popleft()

            if len(queue) >= self._max_requests:
                return False

            queue.append(now)

        return True


_speech_token_rate_limiter = SpeechTokenRateLimiter(
    max_requests=MAX_SPEECH_TOKEN_REQUESTS_PER_MINUTE,
    window_seconds=SPEECH_TOKEN_RATE_LIMIT_WINDOW_SECONDS,
)


def _resolve_rate_limit_key(request: Request) -> str:
    """Resolve best-effort identity key for rate-limiting and telemetry."""
    user_id = request.headers.get(USER_ID_HEADER, "").strip()
    if user_id:
        return f"user:{user_id}"

    if request.client and request.client.host:
        return f"ip:{request.client.host}"

    return "unknown"


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(require_lecture_token)],
)


def get_speech_token_service() -> SpeechTokenService:
    """Dependency provider for speech token issuance service."""
    return AzureSpeechTokenService(
        speech_key=settings.azure_speech_key,
        speech_region=settings.azure_speech_region,
        expires_in_sec=settings.azure_speech_token_expires_in_sec,
        timeout_seconds=settings.azure_speech_sts_timeout_seconds,
    )


@router.get(
    "/speech-token",
    status_code=status.HTTP_200_OK,
    response_model=SpeechTokenResponse,
)
async def get_speech_token(
    request: Request,
    service: Annotated[SpeechTokenService, Depends(get_speech_token_service)],
) -> SpeechTokenResponse:
    """Issue short-lived token for Azure Speech SDK clients."""
    rate_limit_key = _resolve_rate_limit_key(request)
    if not await _speech_token_rate_limiter.allow(rate_limit_key):
        logger.warning(
            "Speech token issuance throttled.",
            extra={"rate_limit_key": rate_limit_key},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many speech token requests.",
        )

    try:
        response = await service.issue_token()
        logger.info(
            "Speech token issued.",
            extra={"rate_limit_key": rate_limit_key},
        )
        return response
    except (SpeechTokenConfigurationError, SpeechTokenProviderError) as exc:
        logger.warning(
            "Speech token issuance failed.",
            extra={
                "rate_limit_key": rate_limit_key,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech token service unavailable.",
        ) from exc

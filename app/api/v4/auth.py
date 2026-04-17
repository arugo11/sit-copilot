"""Auth-related API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.auth import (
    AuthContext,
    build_demo_session_token,
    build_public_demo_user_id,
    require_lecture_token,
    require_public_demo_enabled,
    resolve_auth_context,
    resolve_rate_limit_user_id,
)
from app.core.config import settings
from app.core.rate_limit import (
    RateLimitPolicy,
    SlidingWindowRateLimiter,
    enforce_rate_limit,
)
from app.schemas.demo_auth import DemoSessionBootstrapResponse
from app.schemas.speech_token import SpeechTokenResponse
from app.services.speech_token_service import (
    AzureSpeechTokenService,
    SpeechTokenConfigurationError,
    SpeechTokenProviderError,
    SpeechTokenService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
_demo_bootstrap_rate_limiter = SlidingWindowRateLimiter()
_speech_token_rate_limiter = SlidingWindowRateLimiter()


def get_speech_token_service() -> SpeechTokenService:
    """Dependency provider for speech token issuance service."""
    return AzureSpeechTokenService(
        speech_key=settings.azure_speech_key,
        speech_region=settings.azure_speech_region,
        expires_in_sec=settings.azure_speech_token_expires_in_sec,
        timeout_seconds=settings.azure_speech_sts_timeout_seconds,
    )


@router.post(
    "/demo-session",
    status_code=status.HTTP_200_OK,
    response_model=DemoSessionBootstrapResponse,
    dependencies=[Depends(require_public_demo_enabled)],
)
async def bootstrap_demo_session(
    request: Request,
) -> DemoSessionBootstrapResponse:
    """Issue short-lived public demo credentials."""
    await enforce_rate_limit(
        request,
        limiter=_demo_bootstrap_rate_limiter,
        policy=RateLimitPolicy(
            bucket="demo-bootstrap",
            max_requests=settings.public_demo_rate_limit_bootstrap_per_minute,
        ),
        detail="Too many demo session requests.",
    )
    user_id = build_public_demo_user_id()
    token, expires_at = build_demo_session_token(user_id=user_id)
    return DemoSessionBootstrapResponse(
        lecture_token=token,
        procedure_token=token,
        user_id=user_id,
        expires_at=expires_at,
    )


@router.get(
    "/speech-token",
    status_code=status.HTTP_200_OK,
    response_model=SpeechTokenResponse,
    dependencies=[Depends(require_lecture_token)],
)
async def get_speech_token(
    request: Request,
    auth: Annotated[AuthContext, Depends(resolve_auth_context)],
    service: Annotated[SpeechTokenService, Depends(get_speech_token_service)],
) -> SpeechTokenResponse:
    """Issue short-lived token for Azure Speech SDK clients."""
    await enforce_rate_limit(
        request,
        limiter=_speech_token_rate_limiter,
        policy=RateLimitPolicy(
            bucket="speech-token",
            max_requests=settings.public_demo_rate_limit_lecture_read_per_minute,
        ),
        user_id=resolve_rate_limit_user_id(request, auth),
        detail="Too many speech token requests.",
    )

    try:
        response = await service.issue_token()
        logger.info("Speech token issued.")
        return response
    except (SpeechTokenConfigurationError, SpeechTokenProviderError) as exc:
        logger.warning(
            "Speech token issuance failed.",
            extra={"error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech token service unavailable.",
        ) from exc

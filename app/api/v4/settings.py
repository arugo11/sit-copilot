"""Settings API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthContext,
    require_lecture_token,
    require_user_id,
    resolve_auth_context,
    resolve_rate_limit_user_id,
)
from app.core.config import settings
from app.core.rate_limit import (
    RateLimitPolicy,
    SlidingWindowRateLimiter,
    enforce_rate_limit,
)
from app.db.session import get_db
from app.schemas.settings import SettingsResponse, SettingsUpsertRequest
from app.services.settings_service import SqlAlchemySettingsService

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_lecture_token)],
)
_settings_rate_limiter = SlidingWindowRateLimiter()


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=SettingsResponse,
)
async def get_settings(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(resolve_auth_context)],
    user_id: Annotated[str, Depends(require_user_id)],
) -> SettingsResponse:
    """Get current user's settings."""
    await enforce_rate_limit(
        request,
        limiter=_settings_rate_limiter,
        policy=RateLimitPolicy(
            bucket="settings-get",
            max_requests=settings.public_demo_rate_limit_settings_per_minute,
        ),
        user_id=resolve_rate_limit_user_id(request, auth),
    )
    service = SqlAlchemySettingsService(db)
    return await service.get_my_settings(user_id)


@router.post(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=SettingsResponse,
)
async def upsert_settings(
    http_request: Request,
    request: SettingsUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(resolve_auth_context)],
    user_id: Annotated[str, Depends(require_user_id)],
) -> SettingsResponse:
    """Create or update current user's settings."""
    await enforce_rate_limit(
        http_request,
        limiter=_settings_rate_limiter,
        policy=RateLimitPolicy(
            bucket="settings-upsert",
            max_requests=settings.public_demo_rate_limit_settings_per_minute,
        ),
        user_id=resolve_rate_limit_user_id(http_request, auth),
    )
    service = SqlAlchemySettingsService(db)
    return await service.upsert_my_settings(user_id, request)

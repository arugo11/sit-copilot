"""Settings API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_lecture_token, require_user_id
from app.db.session import get_db
from app.schemas.settings import SettingsResponse, SettingsUpsertRequest
from app.services.settings_service import SqlAlchemySettingsService

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_lecture_token)],
)


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=SettingsResponse,
)
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[str, Depends(require_user_id)],
) -> SettingsResponse:
    """Get current user's settings."""
    service = SqlAlchemySettingsService(db)
    return await service.get_my_settings(user_id)


@router.post(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=SettingsResponse,
)
async def upsert_settings(
    request: SettingsUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[str, Depends(require_user_id)],
) -> SettingsResponse:
    """Create or update current user's settings."""
    service = SqlAlchemySettingsService(db)
    return await service.upsert_my_settings(user_id, request)

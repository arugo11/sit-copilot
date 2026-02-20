"""Settings service for business logic layer."""

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.settings import SettingsResponse, SettingsUpsertRequest

__all__ = ["SettingsService", "SqlAlchemySettingsService"]


class SettingsService(Protocol):
    """Interface for settings operations.

    This Protocol enables easy testing through mock implementations.
    """

    async def get_my_settings(self, user_id: str) -> SettingsResponse:
        """Get user settings. Returns empty dict if not found.

        Args:
            user_id: The user's unique identifier

        Returns:
            SettingsResponse with user_id, settings dict, and updated_at timestamp
        """
        ...

    async def upsert_my_settings(
        self, user_id: str, request: SettingsUpsertRequest
    ) -> SettingsResponse:
        """Create or update user settings.

        Args:
            user_id: The user's unique identifier
            request: Settings upsert request containing settings dict

        Returns:
            SettingsResponse with updated settings and timestamp
        """
        ...


class SqlAlchemySettingsService:
    """SQLAlchemy implementation of SettingsService.

    Handles CRUD operations for user settings using SQLAlchemy async ORM.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session.

        Args:
            db: Async SQLAlchemy session for database operations
        """
        self._db = db

    async def _ensure_user_exists(self, user_id: str) -> None:
        """Create a default user record when it does not exist yet."""
        existing_user = await self._db.get(User, user_id)
        if existing_user is not None:
            return

        user = User(id=user_id)
        self._db.add(user)
        await self._db.flush()

    async def get_my_settings(self, user_id: str) -> SettingsResponse:
        """Get user settings from database.

        Returns empty settings dict if user not found.

        Args:
            user_id: The user's unique identifier

        Returns:
            SettingsResponse with user's settings or empty dict
        """
        result = await self._db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        user_settings = result.scalar_one_or_none()

        if user_settings:
            return SettingsResponse(
                user_id=user_settings.user_id,
                settings=user_settings.settings,
                updated_at=user_settings.updated_at,
            )

        # Return empty settings for non-existent user
        return SettingsResponse(user_id=user_id, settings={}, updated_at=None)

    async def upsert_my_settings(
        self, user_id: str, request: SettingsUpsertRequest
    ) -> SettingsResponse:
        """Create or update user settings in database.

        CRITICAL: Must call flag_modified() after mutating JSON fields
        to ensure SQLAlchemy tracks the change.

        Args:
            user_id: The user's unique identifier
            request: Settings upsert request containing settings dict

        Returns:
            SettingsResponse with updated settings and timestamp
        """
        await self._ensure_user_exists(user_id)
        result = await self._db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        user_settings = result.scalar_one_or_none()

        if user_settings:
            # Update existing settings
            user_settings.settings = request.settings
            # CRITICAL: Required for SQLAlchemy to track JSON mutations
            flag_modified(user_settings, "settings")
        else:
            # Create new user settings
            user_settings = UserSettings(user_id=user_id, settings=request.settings)
            self._db.add(user_settings)

        # Session commit is handled by the get_db() dependency
        await self._db.flush()
        await self._db.refresh(user_settings)

        return SettingsResponse(
            user_id=user_settings.user_id,
            settings=user_settings.settings,
            updated_at=user_settings.updated_at,
        )

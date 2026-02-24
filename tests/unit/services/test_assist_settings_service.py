"""Unit tests for assist settings resolver."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.user import User
from app.models.user_settings import UserSettings
from app.services.assist_settings_service import resolve_assist_generation_settings


@pytest.mark.asyncio
async def test_resolve_assist_generation_settings_defaults_disabled(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Missing user settings should default assist features to disabled."""
    async with session_factory() as session:
        resolved = await resolve_assist_generation_settings(
            session,
            user_id="assist_default_user",
        )

    assert resolved.summary_enabled is False
    assert resolved.keyterms_enabled is False


@pytest.mark.asyncio
async def test_resolve_assist_generation_settings_uses_persisted_flags(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Persisted assist flags should be reflected as runtime settings."""
    user_id = "assist_flags_user"
    async with session_factory() as session:
        session.add(User(id=user_id))
        session.add(
            UserSettings(
                user_id=user_id,
                settings={
                    "assistSummaryEnabled": False,
                    "assistKeytermsEnabled": True,
                },
            )
        )
        await session.flush()

        resolved = await resolve_assist_generation_settings(session, user_id=user_id)

    assert resolved.summary_enabled is False
    assert resolved.keyterms_enabled is True

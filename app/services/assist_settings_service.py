"""Shared resolver for assist generation settings."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.user_id import get_user_id_candidates
from app.models.user_settings import UserSettings

ASSIST_SUMMARY_ENABLED_KEY = "assistSummaryEnabled"
ASSIST_KEYTERMS_ENABLED_KEY = "assistKeytermsEnabled"


@dataclass(frozen=True, slots=True)
class AssistGenerationSettings:
    """Runtime assist feature flags resolved from user settings."""

    summary_enabled: bool
    keyterms_enabled: bool
    summary_available: bool
    keyterms_available: bool


def _as_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _default_enabled_for_public_demo() -> bool:
    return settings.public_demo_enabled


async def resolve_assist_generation_settings(
    db: AsyncSession,
    *,
    user_id: str,
) -> AssistGenerationSettings:
    """Resolve assist generation feature flags for the user."""
    summary_available = (
        settings.azure_openai_enabled and settings.lecture_live_summary_enabled
    )
    keyterms_available = (
        settings.azure_openai_enabled and settings.lecture_live_keyterms_enabled
    )
    user_id_candidates = get_user_id_candidates(user_id)
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id.in_(user_id_candidates))
    )
    settings_rows = list(result.scalars().all())

    settings_model = next(
        (row for row in settings_rows if row.user_id == user_id),
        settings_rows[0] if settings_rows else None,
    )
    user_settings = settings_model.settings if settings_model is not None else None

    if not isinstance(user_settings, dict):
        return AssistGenerationSettings(
            summary_enabled=summary_available and _default_enabled_for_public_demo(),
            keyterms_enabled=keyterms_available
            and _default_enabled_for_public_demo(),
            summary_available=summary_available,
            keyterms_available=keyterms_available,
        )

    return AssistGenerationSettings(
        summary_enabled=summary_available
        and _as_bool(
            user_settings.get(ASSIST_SUMMARY_ENABLED_KEY),
            default=_default_enabled_for_public_demo(),
        ),
        keyterms_enabled=keyterms_available
        and _as_bool(
            user_settings.get(ASSIST_KEYTERMS_ENABLED_KEY),
            default=_default_enabled_for_public_demo(),
        ),
        summary_available=summary_available,
        keyterms_available=keyterms_available,
    )

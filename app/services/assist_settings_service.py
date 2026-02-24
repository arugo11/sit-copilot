"""Shared resolver for assist generation settings."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_id import get_user_id_candidates
from app.models.user_settings import UserSettings

ASSIST_SUMMARY_ENABLED_KEY = "assistSummaryEnabled"
ASSIST_KEYTERMS_ENABLED_KEY = "assistKeytermsEnabled"


@dataclass(frozen=True, slots=True)
class AssistGenerationSettings:
    """Runtime assist feature flags resolved from user settings."""

    summary_enabled: bool
    keyterms_enabled: bool


def _as_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


async def resolve_assist_generation_settings(
    db: AsyncSession,
    *,
    user_id: str,
) -> AssistGenerationSettings:
    """Resolve assist generation feature flags for the user."""
    user_id_candidates = get_user_id_candidates(user_id)
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id.in_(user_id_candidates))
    )
    settings_rows = list(result.scalars().all())

    settings_model = next(
        (row for row in settings_rows if row.user_id == user_id),
        settings_rows[0] if settings_rows else None,
    )
    settings = settings_model.settings if settings_model is not None else None

    if not isinstance(settings, dict):
        return AssistGenerationSettings(
            summary_enabled=False,
            keyterms_enabled=False,
        )

    return AssistGenerationSettings(
        summary_enabled=_as_bool(settings.get(ASSIST_SUMMARY_ENABLED_KEY), default=False),
        keyterms_enabled=_as_bool(settings.get(ASSIST_KEYTERMS_ENABLED_KEY), default=False),
    )

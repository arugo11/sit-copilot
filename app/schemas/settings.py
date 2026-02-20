"""Settings schemas for request/response validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SettingsResponse(BaseModel):
    """Settings response model."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    settings: dict[str, Any]
    updated_at: datetime | None


class SettingsUpsertRequest(BaseModel):
    """Settings upsert request model."""

    model_config = ConfigDict(extra="forbid")

    settings: dict[str, Any]

"""Schemas for public demo session bootstrap."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DemoSessionBootstrapResponse(BaseModel):
    """Response payload for a new public demo session."""

    model_config = ConfigDict(extra="forbid")

    lecture_token: str = Field(min_length=1)
    procedure_token: str = Field(min_length=1)
    user_id: str = Field(min_length=1, max_length=255)
    expires_at: datetime

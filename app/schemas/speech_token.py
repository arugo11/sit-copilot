"""Speech token response schemas."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpeechTokenResponse(BaseModel):
    """Response schema for Azure Speech SDK authorization token issuance."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=4096)
    region: str = Field(min_length=1, max_length=64)
    expires_in_sec: int = Field(gt=0, le=600)

    @field_validator("token", "region")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        """Normalize values and reject blank-only inputs."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be blank.")
        return normalized

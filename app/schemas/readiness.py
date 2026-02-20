"""Readiness check request/response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings

LangMode = Literal["ja", "easy-ja", "en"]


class ReadinessTerm(BaseModel):
    """Readiness glossary term and plain-language explanation."""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=128)
    explanation: str = Field(min_length=1, max_length=240)

    @field_validator("term", "explanation")
    @classmethod
    def validate_text_not_blank(cls, value: str) -> str:
        """Normalize text fields and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("text fields must not be blank.")
        return normalized


class ReadinessCheckRequest(BaseModel):
    """Request schema for course readiness check."""

    model_config = ConfigDict(extra="forbid")

    course_name: str = Field(
        min_length=1,
        max_length=settings.readiness_course_name_max_length,
    )
    syllabus_text: str = Field(
        min_length=1,
        max_length=settings.readiness_syllabus_max_length,
    )
    first_material_blob_path: str | None = Field(
        default=None,
        max_length=settings.readiness_blob_path_max_length,
    )
    lang_mode: LangMode = "ja"
    jp_level_self: int | None = Field(default=None, ge=1, le=5)
    domain_level_self: int | None = Field(default=None, ge=1, le=5)

    @field_validator("course_name", "syllabus_text")
    @classmethod
    def validate_required_text_not_blank(cls, value: str) -> str:
        """Normalize required text fields and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("required text fields must not be blank.")
        return normalized

    @field_validator("first_material_blob_path")
    @classmethod
    def validate_optional_blob_path(cls, value: str | None) -> str | None:
        """Normalize optional blob path and treat blank as None."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized


class ReadinessCheckResponse(BaseModel):
    """Response schema for course readiness check."""

    model_config = ConfigDict(extra="forbid")

    readiness_score: int = Field(ge=0, le=100)
    terms: list[ReadinessTerm] = Field(
        min_length=settings.readiness_terms_min_items,
        max_length=settings.readiness_terms_max_items,
    )
    difficult_points: list[str] = Field(
        min_length=settings.readiness_points_min_items,
        max_length=settings.readiness_points_max_items,
    )
    recommended_settings: list[str] = Field(
        min_length=settings.readiness_points_min_items,
        max_length=settings.readiness_points_max_items,
    )
    prep_tasks: list[str] = Field(
        min_length=settings.readiness_points_min_items,
        max_length=settings.readiness_points_max_items,
    )
    disclaimer: str = Field(min_length=1, max_length=240)

    @field_validator(
        "difficult_points",
        "recommended_settings",
        "prep_tasks",
    )
    @classmethod
    def validate_text_lists_not_blank(cls, values: list[str]) -> list[str]:
        """Normalize list items and reject blank entries."""
        normalized_values = [value.strip() for value in values]
        if any(not value for value in normalized_values):
            raise ValueError("list values must not contain blank text.")
        return normalized_values

    @field_validator("disclaimer")
    @classmethod
    def validate_disclaimer_not_blank(cls, value: str) -> str:
        """Normalize disclaimer and reject blank value."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("disclaimer must not be blank.")
        return normalized

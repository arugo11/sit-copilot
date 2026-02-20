"""Procedure QA request/response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings

ProcedureConfidence = Literal["high", "medium", "low"]
LangMode = Literal["ja", "easy-ja", "en"]


class ProcedureSource(BaseModel):
    """Evidence source item for procedure answer."""

    model_config = ConfigDict(extra="forbid")

    title: str
    section: str
    snippet: str
    source_id: str


class ProcedureAskRequest(BaseModel):
    """Request schema for procedure QA."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=settings.procedure_query_max_length)
    lang_mode: LangMode = "ja"

    @field_validator("query")
    @classmethod
    def validate_query_not_blank(cls, value: str) -> str:
        """Normalize query and reject blank-only payloads."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank.")
        return normalized


class ProcedureAskResponse(BaseModel):
    """Response schema for procedure QA."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    confidence: ProcedureConfidence
    sources: list[ProcedureSource]
    action_next: str
    fallback: str

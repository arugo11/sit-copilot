"""Lecture QA request/response schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LangMode = Literal["ja", "easy-ja", "en"]
LectureQAConfidence = Literal["high", "medium", "low"]
RetrievalMode = Literal["source-only", "source-plus-context"]
LectureSourceType = Literal["speech", "visual"]

MAX_SESSION_ID_LENGTH = 64
MAX_QUESTION_LENGTH = 500
MAX_AUTO_TITLE_DEBUG_EVENT_LENGTH = 64


class LectureSource(BaseModel):
    """BM25 retrieval result with citation info."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    chunk_id: str
    type: LectureSourceType
    text: str
    timestamp: str | None = None  # "MM:SS" format for speech events
    start_ms: int | None = None
    end_ms: int | None = None
    speaker: str | None = None
    bm25_score: float
    is_direct_hit: bool = True  # True if direct match, False if context expansion


class LectureCitation(BaseModel):
    """Citation format for API responses."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    chunk_id: str
    type: LectureSourceType
    timestamp: str | None = None
    text: str  # Snippet (truncated)


class LectureAskRequest(BaseModel):
    """Request schema for /qa/ask."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_LENGTH)
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
    lang_mode: LangMode = "ja"
    retrieval_mode: RetrievalMode = "source-only"
    top_k: int = Field(default=5, ge=1, le=20)
    context_window: int = Field(default=1, ge=0, le=5)  # For source-plus-context

    @field_validator("session_id")
    @classmethod
    def validate_session_id_not_blank(cls, value: str) -> str:
        """Normalize session ID and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id must not be blank.")
        return normalized

    @field_validator("question")
    @classmethod
    def validate_question_not_blank(cls, value: str) -> str:
        """Normalize question and reject blank-only payloads."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank.")
        return normalized


class LectureAskResponse(BaseModel):
    """Response schema for /qa/ask."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    confidence: LectureQAConfidence
    sources: list[LectureSource]
    verification_summary: str | None = None  # Summary of verifier result
    action_next: str
    fallback: str | None = None  # Populated when answer is fallback


class LectureFollowupRequest(BaseModel):
    """Request schema for /qa/followup."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_LENGTH)
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
    lang_mode: LangMode = "ja"
    retrieval_mode: RetrievalMode = "source-only"
    top_k: int = Field(default=5, ge=1, le=20)
    context_window: int = Field(default=1, ge=0, le=5)
    history_turns: int = Field(
        default=3, ge=1, le=10
    )  # Number of previous turns to include

    @field_validator("session_id")
    @classmethod
    def validate_session_id_not_blank(cls, value: str) -> str:
        """Normalize session ID and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id must not be blank.")
        return normalized

    @field_validator("question")
    @classmethod
    def validate_question_not_blank(cls, value: str) -> str:
        """Normalize question and reject blank-only payloads."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank.")
        return normalized


class LectureFollowupResponse(BaseModel):
    """Response schema for /qa/followup."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    confidence: LectureQAConfidence
    sources: list[LectureSource]
    verification_summary: str | None = None
    action_next: str
    fallback: str | None = None
    resolved_query: str  # The standalone query after context resolution


class LectureIndexBuildRequest(BaseModel):
    """Request schema for /qa/index/build."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_LENGTH)
    rebuild: bool = False  # Force rebuild even if index exists

    @field_validator("session_id")
    @classmethod
    def validate_session_id_not_blank(cls, value: str) -> str:
        """Normalize session ID and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id must not be blank.")
        return normalized


class LectureIndexBuildResponse(BaseModel):
    """Response schema for /qa/index/build."""

    model_config = ConfigDict(extra="forbid")

    index_version: str  # UUID or timestamp-based version
    chunk_count: int
    built_at: datetime
    status: Literal["success", "skipped"]  # skipped if already exists and rebuild=False


AutoTitleDebugLogLevel = Literal["info", "warning", "error"]
AutoTitleDebugLocale = Literal["ja", "en"]


class LectureAutoTitleDebugLogRequest(BaseModel):
    """Request schema for auto-title debug logging."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_LENGTH)
    event: str = Field(min_length=1, max_length=MAX_AUTO_TITLE_DEBUG_EVENT_LENGTH)
    level: AutoTitleDebugLogLevel = "info"
    locale: AutoTitleDebugLocale
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("session_id", "event")
    @classmethod
    def validate_log_fields_not_blank(cls, value: str) -> str:
        """Normalize logging fields and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be blank.")
        return normalized


class LectureAutoTitleDebugLogResponse(BaseModel):
    """Response schema for auto-title debug logging."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["logged"]
    log_file: str

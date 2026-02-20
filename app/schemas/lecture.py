"""Lecture live request/response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LangMode = Literal["ja", "easy-ja", "en"]
LectureSpeaker = Literal["teacher", "unknown"]
LectureVisualSource = Literal["slide", "board"]
VisualEventQuality = Literal["good", "warn", "bad"]
LectureEvidenceType = Literal["speech", "slide", "board"]

MAX_SESSION_ID_LENGTH = 64
MAX_TEXT_LENGTH = 5000
MAX_IMAGE_CONTENT_TYPE_LENGTH = 128
MAX_VISUAL_IMAGE_BYTES = 2_000_000
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg"}


class LectureSessionStartRequest(BaseModel):
    """Request schema for starting a lecture live session."""

    model_config = ConfigDict(extra="forbid")

    course_name: str = Field(min_length=1, max_length=255)
    course_id: str | None = Field(default=None, max_length=255)
    lang_mode: LangMode = "ja"
    camera_enabled: bool
    slide_roi: list[int] | None = Field(default=None, min_length=4, max_length=4)
    board_roi: list[int] | None = Field(default=None, min_length=4, max_length=4)
    consent_acknowledged: bool

    @field_validator("course_name")
    @classmethod
    def validate_course_name_not_blank(cls, value: str) -> str:
        """Normalize course name and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("course_name must not be blank.")
        return normalized

    @field_validator("slide_roi", "board_roi")
    @classmethod
    def validate_roi(cls, value: list[int] | None) -> list[int] | None:
        """Ensure ROI coordinates are non-negative and geometrically valid."""
        if value is None:
            return None
        if any(coordinate < 0 for coordinate in value):
            raise ValueError("ROI coordinates must be non-negative.")
        x1, y1, x2, y2 = value
        if x1 >= x2 or y1 >= y2:
            raise ValueError("ROI coordinates must satisfy x1 < x2 and y1 < y2.")
        return value

    @field_validator("consent_acknowledged")
    @classmethod
    def validate_consent_acknowledged(cls, value: bool) -> bool:
        """Lecture session start requires explicit consent acknowledgment."""
        if not value:
            raise ValueError("consent_acknowledged must be true.")
        return value


class LectureSessionStartResponse(BaseModel):
    """Response schema for starting a lecture session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    status: Literal["active"]


class SpeechChunkIngestRequest(BaseModel):
    """Request schema for finalized subtitle event ingestion."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_LENGTH)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    confidence: float = Field(ge=0.0, le=1.0)
    is_final: bool
    speaker: LectureSpeaker

    @field_validator("session_id")
    @classmethod
    def validate_session_id_not_blank(cls, value: str) -> str:
        """Normalize session ID and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id must not be blank.")
        return normalized

    @field_validator("text")
    @classmethod
    def validate_text_not_blank(cls, value: str) -> str:
        """Normalize text and reject blank-only subtitles."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_time_range_and_finality(self) -> "SpeechChunkIngestRequest":
        """Ensure timing and final-event constraints for persistence."""
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms must be greater than or equal to start_ms.")
        if not self.is_final:
            raise ValueError("only finalized speech events can be ingested.")
        return self


class SpeechChunkIngestResponse(BaseModel):
    """Response schema for speech event ingestion acknowledgement."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    session_id: str
    accepted: bool


class VisualEventIngestRequest(BaseModel):
    """Request schema for OCR visual event ingestion."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_LENGTH)
    timestamp_ms: int = Field(ge=0)
    source: LectureVisualSource
    change_score: float = Field(ge=0.0, le=1.0)
    image_content_type: str = Field(
        min_length=1,
        max_length=MAX_IMAGE_CONTENT_TYPE_LENGTH,
    )
    image_size: int = Field(gt=0)
    upload_size_limit: int = Field(gt=0, le=MAX_VISUAL_IMAGE_BYTES)
    image_has_jpeg_magic: bool

    @field_validator("session_id")
    @classmethod
    def validate_session_id_not_blank(cls, value: str) -> str:
        """Normalize session ID and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id must not be blank.")
        return normalized

    @field_validator("image_content_type")
    @classmethod
    def validate_image_content_type(cls, value: str) -> str:
        """Allow only JPEG content types for MVP ingestion."""
        normalized = value.strip().lower()
        if normalized not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValueError("image_content_type must be image/jpeg.")
        return normalized

    @field_validator("image_has_jpeg_magic")
    @classmethod
    def validate_image_has_jpeg_magic(cls, value: bool) -> bool:
        """Ensure the uploaded payload has JPEG magic bytes."""
        if not value:
            raise ValueError("image payload must be a valid JPEG.")
        return value

    @model_validator(mode="after")
    def validate_image_size_within_upload_limit(self) -> "VisualEventIngestRequest":
        """Ensure uploaded image stays within configured size limit."""
        if self.image_size > self.upload_size_limit:
            raise ValueError(
                f"image_size must be less than or equal to {self.upload_size_limit}."
            )
        return self


class VisualEventIngestResponse(BaseModel):
    """Response schema for OCR visual event ingestion."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    ocr_text: str
    ocr_confidence: float = Field(ge=0.0, le=1.0)
    quality: VisualEventQuality


class LectureSummaryKeyTerm(BaseModel):
    """Summary key term with source evidence tags."""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=128)
    evidence_tags: list[LectureEvidenceType] = Field(min_length=1, max_length=3)

    @field_validator("term")
    @classmethod
    def validate_term_not_blank(cls, value: str) -> str:
        """Normalize term and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("term must not be blank.")
        return normalized


class LectureSummaryEvidence(BaseModel):
    """Evidence reference used in lecture summary response."""

    model_config = ConfigDict(extra="forbid")

    type: LectureEvidenceType
    ref_id: str = Field(min_length=1, max_length=64)

    @field_validator("ref_id")
    @classmethod
    def validate_ref_id_not_blank(cls, value: str) -> str:
        """Normalize evidence reference ID and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("ref_id must not be blank.")
        return normalized


class LectureSummaryLatestResponse(BaseModel):
    """Response schema for the latest 30-second lecture summary window."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    window_start_ms: int = Field(ge=0)
    window_end_ms: int = Field(ge=0)
    summary: str
    key_terms: list[LectureSummaryKeyTerm]
    evidence: list[LectureSummaryEvidence]
    status: Literal["ok", "no_data"] = "ok"


class LectureSessionFinalizeRequest(BaseModel):
    """Request schema for lecture session finalization."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_LENGTH)
    build_qa_index: bool = True

    @field_validator("session_id")
    @classmethod
    def validate_session_id_not_blank(cls, value: str) -> str:
        """Normalize session ID and reject blank values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id must not be blank.")
        return normalized


class LectureSessionFinalizeStats(BaseModel):
    """Artifact counts created by session finalization."""

    model_config = ConfigDict(extra="forbid")

    speech_events: int = Field(ge=0)
    visual_events: int = Field(ge=0)
    summary_windows: int = Field(ge=0)
    lecture_chunks: int = Field(ge=0)


class LectureSessionFinalizeResponse(BaseModel):
    """Response schema for lecture session finalization."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    status: Literal["finalized"]
    note_generated: bool
    qa_index_built: bool
    stats: LectureSessionFinalizeStats

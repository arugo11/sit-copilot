"""Pydantic schemas for request/response validation."""

from app.schemas.error import ErrorResponse
from app.schemas.health import HealthResponse
from app.schemas.lecture import (
    LectureSessionStartRequest,
    LectureSessionStartResponse,
    SpeechChunkIngestRequest,
    SpeechChunkIngestResponse,
    VisualEventIngestRequest,
    VisualEventIngestResponse,
)
from app.schemas.lecture_qa import (
    LectureAskRequest,
    LectureAskResponse,
    LectureCitation,
    LectureFollowupRequest,
    LectureFollowupResponse,
    LectureIndexBuildRequest,
    LectureIndexBuildResponse,
    LectureSource,
)
from app.schemas.procedure import (
    ProcedureAskRequest,
    ProcedureAskResponse,
    ProcedureSource,
)
from app.schemas.readiness import (
    ReadinessCheckRequest,
    ReadinessCheckResponse,
    ReadinessTerm,
)
from app.schemas.settings import SettingsResponse, SettingsUpsertRequest

__all__ = [
    "ErrorResponse",
    "HealthResponse",
    "LectureAskRequest",
    "LectureAskResponse",
    "LectureCitation",
    "LectureFollowupRequest",
    "LectureFollowupResponse",
    "LectureIndexBuildRequest",
    "LectureIndexBuildResponse",
    "LectureSessionStartRequest",
    "LectureSessionStartResponse",
    "ProcedureAskRequest",
    "ProcedureAskResponse",
    "ProcedureSource",
    "ReadinessCheckRequest",
    "ReadinessCheckResponse",
    "ReadinessTerm",
    "LectureSource",
    "SpeechChunkIngestRequest",
    "SpeechChunkIngestResponse",
    "VisualEventIngestRequest",
    "VisualEventIngestResponse",
    "SettingsResponse",
    "SettingsUpsertRequest",
]

"""Unit tests for lecture live schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.lecture import (
    MAX_VISUAL_IMAGE_BYTES,
    LectureSessionStartRequest,
    SpeechChunkIngestRequest,
    VisualEventIngestRequest,
)


def test_lecture_session_start_request_accepts_valid_payload() -> None:
    """LectureSessionStartRequest should accept a valid payload."""
    payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }

    request = LectureSessionStartRequest.model_validate(payload)

    assert request.course_name == payload["course_name"]
    assert request.lang_mode == payload["lang_mode"]
    assert request.consent_acknowledged is True


def test_lecture_session_start_request_rejects_false_consent() -> None:
    """LectureSessionStartRequest should require consent acknowledgement."""
    payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": False,
    }

    with pytest.raises(ValidationError):
        LectureSessionStartRequest.model_validate(payload)


def test_lecture_session_start_request_rejects_negative_roi() -> None:
    """LectureSessionStartRequest should reject negative ROI coordinates."""
    payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [-1, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }

    with pytest.raises(ValidationError):
        LectureSessionStartRequest.model_validate(payload)


def test_lecture_session_start_request_rejects_inverted_roi_geometry() -> None:
    """LectureSessionStartRequest should reject inverted ROI geometry."""
    payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [900, 80, 100, 520],
        "board_roi": [80, 980, 920, 560],
        "consent_acknowledged": True,
    }

    with pytest.raises(ValidationError):
        LectureSessionStartRequest.model_validate(payload)


def test_speech_chunk_ingest_request_accepts_valid_payload() -> None:
    """SpeechChunkIngestRequest should accept valid finalized chunk payload."""
    payload = {
        "session_id": "lec_20260220_ab12cd",
        "start_ms": 15000,
        "end_ms": 20000,
        "text": "外れ値がある場合は散布図で確認します。",
        "confidence": 0.93,
        "is_final": True,
        "speaker": "teacher",
    }

    request = SpeechChunkIngestRequest.model_validate(payload)

    assert request.session_id == payload["session_id"]
    assert request.start_ms == payload["start_ms"]
    assert request.end_ms == payload["end_ms"]


def test_speech_chunk_ingest_request_rejects_invalid_time_range() -> None:
    """SpeechChunkIngestRequest should reject end_ms earlier than start_ms."""
    payload = {
        "session_id": "lec_20260220_ab12cd",
        "start_ms": 20000,
        "end_ms": 15000,
        "text": "外れ値がある場合は散布図で確認します。",
        "confidence": 0.93,
        "is_final": True,
        "speaker": "teacher",
    }

    with pytest.raises(ValidationError):
        SpeechChunkIngestRequest.model_validate(payload)


def test_speech_chunk_ingest_request_rejects_non_final_event() -> None:
    """SpeechChunkIngestRequest should reject non-final subtitle chunks."""
    payload = {
        "session_id": "lec_20260220_ab12cd",
        "start_ms": 15000,
        "end_ms": 20000,
        "text": "外れ値がある場合は散布図で確認します。",
        "confidence": 0.93,
        "is_final": False,
        "speaker": "teacher",
    }

    with pytest.raises(ValidationError):
        SpeechChunkIngestRequest.model_validate(payload)


def test_visual_event_ingest_request_accepts_valid_payload() -> None:
    """VisualEventIngestRequest should accept valid multipart-derived fields."""
    payload = {
        "session_id": "lec_20260220_ab12cd",
        "timestamp_ms": 18000,
        "source": "slide",
        "change_score": 0.42,
        "image_content_type": "image/jpeg",
        "image_size": 1024,
        "upload_size_limit": MAX_VISUAL_IMAGE_BYTES,
        "image_has_jpeg_magic": True,
    }

    request = VisualEventIngestRequest.model_validate(payload)

    assert request.session_id == payload["session_id"]
    assert request.source == payload["source"]
    assert request.change_score == payload["change_score"]


def test_visual_event_ingest_request_rejects_blank_session_id() -> None:
    """VisualEventIngestRequest should reject blank session IDs."""
    payload = {
        "session_id": "   ",
        "timestamp_ms": 18000,
        "source": "slide",
        "change_score": 0.42,
        "image_content_type": "image/jpeg",
        "image_size": 1024,
        "upload_size_limit": MAX_VISUAL_IMAGE_BYTES,
        "image_has_jpeg_magic": True,
    }

    with pytest.raises(ValidationError):
        VisualEventIngestRequest.model_validate(payload)


def test_visual_event_ingest_request_rejects_unsupported_content_type() -> None:
    """VisualEventIngestRequest should reject non-JPEG uploads."""
    payload = {
        "session_id": "lec_20260220_ab12cd",
        "timestamp_ms": 18000,
        "source": "board",
        "change_score": 0.42,
        "image_content_type": "image/png",
        "image_size": 1024,
        "upload_size_limit": MAX_VISUAL_IMAGE_BYTES,
        "image_has_jpeg_magic": True,
    }

    with pytest.raises(ValidationError):
        VisualEventIngestRequest.model_validate(payload)


def test_visual_event_ingest_request_rejects_empty_image() -> None:
    """VisualEventIngestRequest should reject empty file payloads."""
    payload = {
        "session_id": "lec_20260220_ab12cd",
        "timestamp_ms": 18000,
        "source": "board",
        "change_score": 0.42,
        "image_content_type": "image/jpeg",
        "image_size": 0,
        "upload_size_limit": MAX_VISUAL_IMAGE_BYTES,
        "image_has_jpeg_magic": True,
    }

    with pytest.raises(ValidationError):
        VisualEventIngestRequest.model_validate(payload)


def test_visual_event_ingest_request_rejects_invalid_jpeg_magic() -> None:
    """VisualEventIngestRequest should reject non-JPEG payload signature."""
    payload = {
        "session_id": "lec_20260220_ab12cd",
        "timestamp_ms": 18000,
        "source": "board",
        "change_score": 0.42,
        "image_content_type": "image/jpeg",
        "image_size": 1024,
        "upload_size_limit": MAX_VISUAL_IMAGE_BYTES,
        "image_has_jpeg_magic": False,
    }

    with pytest.raises(ValidationError):
        VisualEventIngestRequest.model_validate(payload)


def test_visual_event_ingest_request_rejects_oversized_image() -> None:
    """VisualEventIngestRequest should reject payload over upload limit."""
    payload = {
        "session_id": "lec_20260220_ab12cd",
        "timestamp_ms": 18000,
        "source": "board",
        "change_score": 0.42,
        "image_content_type": "image/jpeg",
        "image_size": MAX_VISUAL_IMAGE_BYTES + 1,
        "upload_size_limit": MAX_VISUAL_IMAGE_BYTES,
        "image_has_jpeg_magic": True,
    }

    with pytest.raises(ValidationError):
        VisualEventIngestRequest.model_validate(payload)

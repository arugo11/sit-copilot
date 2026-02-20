"""Unit tests for readiness schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.readiness import (
    ReadinessCheckRequest,
    ReadinessCheckResponse,
    ReadinessTerm,
)


def _build_terms(count: int) -> list[dict[str, str]]:
    return [
        {
            "term": f"用語{index}",
            "explanation": f"用語{index}の説明",
        }
        for index in range(count)
    ]


def test_readiness_check_request_accepts_valid_payload() -> None:
    """ReadinessCheckRequest should accept valid payload."""
    payload = {
        "course_name": "統計学基礎",
        "syllabus_text": "回帰分析と分散分析を扱います。",
        "first_material_blob_path": "  path/to/material.pdf  ",
        "lang_mode": "ja",
        "jp_level_self": 3,
        "domain_level_self": 2,
    }

    request = ReadinessCheckRequest.model_validate(payload)

    assert request.course_name == "統計学基礎"
    assert request.syllabus_text == "回帰分析と分散分析を扱います。"
    assert request.first_material_blob_path == "path/to/material.pdf"


def test_readiness_check_request_rejects_extra_fields() -> None:
    """ReadinessCheckRequest should reject unknown fields."""
    payload = {
        "course_name": "統計学基礎",
        "syllabus_text": "回帰分析を扱います。",
        "lang_mode": "ja",
        "unexpected": "value",
    }

    with pytest.raises(ValidationError):
        ReadinessCheckRequest.model_validate(payload)


def test_readiness_check_request_rejects_invalid_self_levels() -> None:
    """ReadinessCheckRequest should reject out-of-range self levels."""
    payload = {
        "course_name": "統計学基礎",
        "syllabus_text": "回帰分析を扱います。",
        "lang_mode": "ja",
        "jp_level_self": 6,
    }

    with pytest.raises(ValidationError):
        ReadinessCheckRequest.model_validate(payload)


def test_readiness_check_response_requires_terms_min_length() -> None:
    """ReadinessCheckResponse should enforce minimum term count."""
    payload = {
        "readiness_score": 68,
        "terms": _build_terms(1),
        "difficult_points": ["A", "B"],
        "recommended_settings": ["字幕ON", "板書OCRON"],
        "prep_tasks": ["用語確認", "前提復習"],
        "disclaimer": "この結果は履修準備の目安です.",
    }

    with pytest.raises(ValidationError):
        ReadinessCheckResponse.model_validate(payload)


def test_readiness_term_rejects_blank_explanation() -> None:
    """ReadinessTerm should reject blank explanation."""
    with pytest.raises(ValidationError):
        ReadinessTerm.model_validate(
            {
                "term": "回帰分析",
                "explanation": "   ",
            }
        )

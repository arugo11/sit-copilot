"""Unit tests for readiness service."""

import pytest

from app.core.config import settings
from app.schemas.readiness import ReadinessCheckRequest
from app.services.readiness_service import DeterministicReadinessService


def _build_request(
    *,
    jp_level_self: int | None = 3,
    domain_level_self: int | None = 3,
) -> ReadinessCheckRequest:
    return ReadinessCheckRequest(
        course_name="統計学基礎",
        syllabus_text=(
            "この授業では回帰分析と分散分析を扱います。"
            "前提知識として線形代数の理解を求めます。"
            "課題レポートと口頭発表があります。"
        ),
        first_material_blob_path=None,
        lang_mode="ja",
        jp_level_self=jp_level_self,
        domain_level_self=domain_level_self,
    )


@pytest.mark.asyncio
async def test_check_returns_contract_safe_response() -> None:
    """check should return response with contract-compliant field bounds."""
    service = DeterministicReadinessService()

    response = await service.check(_build_request())

    assert 0 <= response.readiness_score <= 100
    assert settings.readiness_terms_min_items <= len(response.terms)
    assert len(response.terms) <= settings.readiness_terms_max_items
    assert settings.readiness_points_min_items <= len(response.difficult_points)
    assert len(response.difficult_points) <= settings.readiness_points_max_items
    assert settings.readiness_points_min_items <= len(response.recommended_settings)
    assert len(response.recommended_settings) <= settings.readiness_points_max_items
    assert settings.readiness_points_min_items <= len(response.prep_tasks)
    assert len(response.prep_tasks) <= settings.readiness_points_max_items
    assert response.disclaimer == settings.readiness_default_disclaimer


@pytest.mark.asyncio
async def test_check_is_deterministic_for_same_input() -> None:
    """check should return identical response for identical inputs."""
    service = DeterministicReadinessService()
    request = _build_request()

    first = await service.check(request)
    second = await service.check(request)

    assert first.model_dump() == second.model_dump()


@pytest.mark.asyncio
async def test_check_reflects_self_level_risk_adjustment() -> None:
    """Lower self-level inputs should produce higher readiness risk score."""
    service = DeterministicReadinessService()
    low_level_response = await service.check(
        _build_request(jp_level_self=1, domain_level_self=1)
    )
    high_level_response = await service.check(
        _build_request(jp_level_self=5, domain_level_self=5)
    )

    assert low_level_response.readiness_score > high_level_response.readiness_score


@pytest.mark.asyncio
async def test_check_returns_terms_with_blank_material_path() -> None:
    """Blank optional path should be normalized and still return full response."""
    service = DeterministicReadinessService()
    request = ReadinessCheckRequest(
        course_name="情報基礎",
        syllabus_text="基礎用語と演習を中心に学びます。",
        first_material_blob_path="   ",
        lang_mode="easy-ja",
        jp_level_self=None,
        domain_level_self=None,
    )

    response = await service.check(request)

    assert response.terms
    assert response.difficult_points
    assert response.recommended_settings
    assert response.prep_tasks


@pytest.mark.asyncio
async def test_check_matches_english_keywords_case_insensitively() -> None:
    """English keywords should be matched regardless of input letter case."""
    service = DeterministicReadinessService()
    request = ReadinessCheckRequest(
        course_name="Academic Writing",
        syllabus_text=(
            "this course requires prerequisite knowledge and a final REPORT essay."
        ),
        first_material_blob_path=None,
        lang_mode="en",
        jp_level_self=None,
        domain_level_self=None,
    )

    response = await service.check(request)

    assert any("前提知識を前提に進む可能性" in point for point in response.difficult_points)
    assert any("記述課題の比重が高く" in point for point in response.difficult_points)
    assert "やさしい日本語要約" in response.recommended_settings
    assert "用語説明を詳細表示" in response.recommended_settings

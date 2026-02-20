"""Integration tests for readiness API endpoint."""

import pytest
from httpx import AsyncClient

from app.core.auth import LECTURE_TOKEN_HEADER
from app.core.config import settings

AUTH_HEADERS = {LECTURE_TOKEN_HEADER: settings.lecture_api_token}


@pytest.mark.asyncio
async def test_post_readiness_check_returns_200_with_required_fields(
    async_client: AsyncClient,
) -> None:
    """Readiness endpoint should return contract-safe response."""
    payload = {
        "course_name": "統計学基礎",
        "syllabus_text": (
            "この授業では回帰分析と分散分析を扱います。"
            "前提知識として線形代数を求め、課題レポートがあります。"
        ),
        "first_material_blob_path": None,
        "lang_mode": "ja",
        "jp_level_self": 3,
        "domain_level_self": 2,
    }

    response = await async_client.post(
        "/api/v4/course/readiness/check",
        json=payload,
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert 0 <= body["readiness_score"] <= 100
    assert len(body["terms"]) >= settings.readiness_terms_min_items
    assert len(body["terms"]) <= settings.readiness_terms_max_items
    assert len(body["difficult_points"]) >= settings.readiness_points_min_items
    assert len(body["difficult_points"]) <= settings.readiness_points_max_items
    assert len(body["recommended_settings"]) >= settings.readiness_points_min_items
    assert len(body["recommended_settings"]) <= settings.readiness_points_max_items
    assert len(body["prep_tasks"]) >= settings.readiness_points_min_items
    assert len(body["prep_tasks"]) <= settings.readiness_points_max_items
    assert body["disclaimer"] != ""


@pytest.mark.asyncio
async def test_post_readiness_check_with_invalid_payload_returns_400(
    async_client: AsyncClient,
) -> None:
    """Validation failures should return common 400 error response."""
    response = await async_client.post(
        "/api/v4/course/readiness/check",
        json={
            "course_name": "統計学基礎",
            "lang_mode": "ja",
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_post_readiness_check_without_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Readiness endpoint should reject requests without auth token."""
    response = await async_client.post(
        "/api/v4/course/readiness/check",
        json={
            "course_name": "統計学基礎",
            "syllabus_text": "回帰分析を扱います。",
            "lang_mode": "ja",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_readiness_check_is_deterministic(
    async_client: AsyncClient,
) -> None:
    """Same payload should produce identical readiness result."""
    payload = {
        "course_name": "統計学基礎",
        "syllabus_text": "回帰分析と線形代数を扱い、発表があります。",
        "first_material_blob_path": "lecture/first.pdf",
        "lang_mode": "ja",
        "jp_level_self": 2,
        "domain_level_self": 2,
    }

    first = await async_client.post(
        "/api/v4/course/readiness/check",
        json=payload,
        headers=AUTH_HEADERS,
    )
    second = await async_client.post(
        "/api/v4/course/readiness/check",
        json=payload,
        headers=AUTH_HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

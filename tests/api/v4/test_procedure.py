"""Integration tests for procedure QA API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth import PROCEDURE_TOKEN_HEADER
from app.core.config import settings
from app.models.qa_turn import QATurn

AUTH_HEADERS = {PROCEDURE_TOKEN_HEADER: settings.procedure_api_token}


@pytest.mark.asyncio
async def test_post_procedure_ask_with_evidence_returns_sources_and_persists(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Known query should return sources and save a qa_turn row."""
    payload = {
        "query": "在学証明書はどこで発行できますか。",
        "lang_mode": "ja",
    }

    response = await async_client.post(
        "/api/v4/procedure/ask", json=payload, headers=AUTH_HEADERS
    )
    body = response.json()

    assert response.status_code == 200
    assert body["confidence"] in {"high", "medium", "low"}
    assert isinstance(body["sources"], list)
    assert len(body["sources"]) > 0
    assert body["action_next"] != ""
    assert body["fallback"] == ""

    async with session_factory() as session:
        result = await session.execute(
            select(QATurn).where(QATurn.question == payload["query"])
        )
        qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.feature == "procedure_qa"


@pytest.mark.asyncio
async def test_post_procedure_ask_without_evidence_returns_fallback_and_persists(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Unknown query should return fallback and still save a qa_turn row."""
    payload = {
        "query": "この質問は根拠が見つからない想定です",
        "lang_mode": "ja",
    }

    response = await async_client.post(
        "/api/v4/procedure/ask", json=payload, headers=AUTH_HEADERS
    )
    body = response.json()

    assert response.status_code == 200
    assert body["confidence"] == "low"
    assert body["sources"] == []
    assert body["action_next"] != ""
    assert body["fallback"] != ""

    async with session_factory() as session:
        result = await session.execute(
            select(QATurn).where(QATurn.question == payload["query"])
        )
        qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.feature == "procedure_qa"


@pytest.mark.asyncio
async def test_post_procedure_ask_with_invalid_payload_returns_400(
    async_client: AsyncClient,
) -> None:
    """Validation failures should return common 400 error response."""
    response = await async_client.post(
        "/api/v4/procedure/ask",
        json={"lang_mode": "ja"},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_post_procedure_ask_with_invalid_lang_mode_returns_400(
    async_client: AsyncClient,
) -> None:
    """Invalid lang_mode should fail validation."""
    response = await async_client.post(
        "/api/v4/procedure/ask",
        json={"query": "在学証明書はどこですか。", "lang_mode": "fr"},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_post_procedure_ask_without_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Procedure endpoint should reject requests without auth token."""
    response = await async_client.post(
        "/api/v4/procedure/ask",
        json={"query": "在学証明書はどこですか。", "lang_mode": "ja"},
    )

    assert response.status_code == 401

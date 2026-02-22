"""Integration tests for procedure QA API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v4 import procedure as procedure_api
from app.core.auth import PROCEDURE_TOKEN_HEADER
from app.core.config import settings
from app.main import app
from app.models.qa_turn import QATurn
from app.schemas.procedure import ProcedureSource
from app.services.procedure_answerer_service import (
    ProcedureAnswerDraft,
    ProcedureAnswererError,
)
from app.services.lecture_verifier_service import LectureVerificationResult
from app.services.procedure_retrieval_service import (
    AzureSearchProcedureRetrievalService,
    NoopProcedureRetrievalService,
)

AUTH_HEADERS = {PROCEDURE_TOKEN_HEADER: settings.procedure_api_token}


class StubRetriever:
    """Retriever test double returning fixed sources."""

    def __init__(self, sources: list[ProcedureSource]) -> None:
        self._sources = sources

    async def retrieve(
        self, query: str, lang_mode: str, limit: int = 3
    ) -> list[ProcedureSource]:
        _ = (query, lang_mode, limit)
        return self._sources


class SpyAnswerer:
    """Answerer test double with invocation tracking."""

    def __init__(self, draft: ProcedureAnswerDraft) -> None:
        self._draft = draft
        self.call_count = 0

    async def answer(
        self, query: str, lang_mode: str, sources: list[ProcedureSource]
    ) -> ProcedureAnswerDraft:
        _ = (query, lang_mode, sources)
        self.call_count += 1
        return self._draft


class ErrorAnswerer:
    """Answerer test double that raises ProcedureAnswererError."""

    async def answer(
        self, query: str, lang_mode: str, sources: list[ProcedureSource]
    ) -> ProcedureAnswerDraft:
        _ = (query, lang_mode, sources)
        raise ProcedureAnswererError("failed")


class PassVerifier:
    """Verifier test double that always passes."""

    async def verify(
        self,
        question: str,
        answer: str,
        sources: list,
    ) -> LectureVerificationResult:
        _ = (question, answer, sources)
        return LectureVerificationResult(
            passed=True,
            summary="verified",
            unsupported_claims=[],
        )

    async def repair_answer(
        self,
        question: str,
        answer: str,
        sources: list,
        unsupported_claims: list[str],
    ) -> str | None:
        _ = (question, answer, sources, unsupported_claims)
        return None


@pytest.mark.asyncio
async def test_post_procedure_ask_with_evidence_returns_sources_and_persists(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Known query should return sources and save a qa_turn row."""
    sources = [
        ProcedureSource(
            title="証明書発行案内",
            section="申請方法",
            snippet="在学証明書は証明書発行機で発行できます。",
            source_id="doc_012_c03",
        )
    ]
    app.dependency_overrides[procedure_api.get_procedure_retrieval_service] = lambda: (
        StubRetriever(sources)
    )
    app.dependency_overrides[procedure_api.get_procedure_answerer_service] = lambda: (
        SpyAnswerer(
            ProcedureAnswerDraft(
                answer="在学証明書は証明書発行機で発行できます。",
                confidence="high",
                action_next="学生証を持って証明書発行機を利用してください。",
            )
        )
    )
    app.dependency_overrides[procedure_api.get_procedure_verifier_service] = lambda: (
        PassVerifier()
    )

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
    assert body["sources"] != []
    assert body["action_next"] != ""
    assert body["fallback"] == ""

    async with session_factory() as session:
        result = await session.execute(
            select(QATurn).where(QATurn.question == payload["query"])
        )
        qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.feature == "procedure_qa"
    assert qa_turn.citations_json == [sources[0].model_dump()]
    assert qa_turn.retrieved_chunk_ids_json == ["doc_012_c03"]


@pytest.mark.asyncio
async def test_post_procedure_ask_without_evidence_returns_fallback_and_persists(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Unknown query should return fallback and still save a qa_turn row."""
    answerer = SpyAnswerer(
        ProcedureAnswerDraft(
            answer="unused",
            confidence="medium",
            action_next="unused",
        )
    )
    app.dependency_overrides[procedure_api.get_procedure_retrieval_service] = lambda: (
        StubRetriever([])
    )
    app.dependency_overrides[procedure_api.get_procedure_answerer_service] = lambda: (
        answerer
    )
    app.dependency_overrides[procedure_api.get_procedure_verifier_service] = lambda: (
        PassVerifier()
    )

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
    assert answerer.call_count == 0

    async with session_factory() as session:
        result = await session.execute(
            select(QATurn).where(QATurn.question == payload["query"])
        )
        qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.feature == "procedure_qa"
    assert qa_turn.citations_json == []
    assert qa_turn.retrieved_chunk_ids_json == []


@pytest.mark.asyncio
async def test_post_procedure_ask_with_answerer_failure_returns_local_grounded_answer(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Answerer failure should still return 200 with local grounded answer."""
    sources = [
        ProcedureSource(
            title="証明書発行案内",
            section="申請方法",
            snippet="在学証明書は証明書発行機で発行できます。",
            source_id="doc_012_c03",
        )
    ]
    app.dependency_overrides[procedure_api.get_procedure_retrieval_service] = lambda: (
        StubRetriever(sources)
    )
    app.dependency_overrides[procedure_api.get_procedure_answerer_service] = lambda: (
        ErrorAnswerer()
    )
    app.dependency_overrides[procedure_api.get_procedure_verifier_service] = lambda: (
        PassVerifier()
    )

    payload = {
        "query": "在学証明書はどこで発行できますか。",
        "lang_mode": "ja",
    }
    response = await async_client.post(
        "/api/v4/procedure/ask", json=payload, headers=AUTH_HEADERS
    )
    body = response.json()

    assert response.status_code == 200
    assert body["confidence"] == "low"
    assert body["sources"] != []
    assert body["fallback"] == ""
    assert body["answer"].startswith("根拠資料から確認できる内容です。")
    assert "doc_012_c03" in body["answer"]

    async with session_factory() as session:
        result = await session.execute(
            select(QATurn).where(QATurn.question == payload["query"])
        )
        qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.feature == "procedure_qa"
    assert qa_turn.citations_json == [sources[0].model_dump()]
    assert qa_turn.retrieved_chunk_ids_json == ["doc_012_c03"]


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


def test_get_procedure_retrieval_service_uses_azure_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieval provider should switch to Azure adapter when enabled."""
    monkeypatch.setattr(settings, "azure_search_enabled", True)
    monkeypatch.setattr(
        settings,
        "azure_search_endpoint",
        "https://example.search.windows.net",
    )
    monkeypatch.setattr(settings, "azure_search_api_key", "dummy-key")

    service = procedure_api.get_procedure_retrieval_service()

    assert isinstance(service, AzureSearchProcedureRetrievalService)


def test_get_procedure_retrieval_service_falls_back_to_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieval provider should use Noop retriever when Azure is disabled."""
    monkeypatch.setattr(settings, "azure_search_enabled", False)
    monkeypatch.setattr(settings, "azure_search_endpoint", "")
    monkeypatch.setattr(settings, "azure_search_api_key", "")

    service = procedure_api.get_procedure_retrieval_service()

    assert isinstance(service, NoopProcedureRetrievalService)

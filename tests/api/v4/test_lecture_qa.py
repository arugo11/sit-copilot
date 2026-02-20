"""Integration tests for lecture QA API endpoints."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v4 import lecture_qa as lecture_qa_api
from app.core.auth import LECTURE_TOKEN_HEADER, USER_ID_HEADER
from app.core.config import settings
from app.models.qa_turn import QATurn
from app.services.lecture_retrieval_service import (
    AzureSearchLectureRetrievalService,
    BM25LectureRetrievalService,
)

AUTH_HEADERS = {
    LECTURE_TOKEN_HEADER: settings.lecture_api_token,
    USER_ID_HEADER: "test_user",
}


class FakeAzureSearchService:
    """Azure search test double for API dependency overrides."""

    def __init__(
        self,
        *,
        documents: list[dict[str, Any]] | None = None,
        succeeded_chunk_ids: list[str] | None = None,
        fail_search: bool = False,
    ) -> None:
        self.documents = documents or []
        self.succeeded_chunk_ids = succeeded_chunk_ids
        self.fail_search = fail_search
        self.upsert_calls: list[list[dict[str, Any]]] = []

    async def ensure_lecture_index(self) -> None:
        """No-op for tests."""

    async def upsert_lecture_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> list[str]:
        self.upsert_calls.append(documents)
        if self.succeeded_chunk_ids is not None:
            return self.succeeded_chunk_ids
        return [str(document["chunk_id"]) for document in documents]

    async def search_lecture_documents(
        self,
        *,
        search_text: str,
        session_id: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        _ = (search_text, session_id, top_k)
        if self.fail_search:
            raise RuntimeError("azure search query failed")
        return self.documents[:top_k]

    async def list_session_documents(
        self,
        *,
        session_id: str,
        max_documents: int = 1000,
    ) -> list[dict[str, Any]]:
        _ = (session_id, max_documents)
        return self.documents[:max_documents]

    async def has_session_documents(self, *, session_id: str) -> bool:
        _ = session_id
        return bool(self.documents)


@pytest.mark.asyncio
async def test_post_qa_index_build_returns_success(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Index build should return success response."""
    # First, create a lecture session with speech events
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession
        from app.models.speech_event import SpeechEvent

        session_id = "test_session_qa_001"
        session_obj = LectureSession(
            id=session_id,
            user_id="test_user",
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
            qa_index_built=False,
        )
        session.add(session_obj)

        # Add some speech events
        for i in range(3):
            event = SpeechEvent(
                session_id=session_id,
                start_ms=i * 10000,
                end_ms=(i + 1) * 10000,
                text=f"Test speech content {i + 1}",
                confidence=0.95,
                is_final=True,
                speaker="teacher",
            )
            session.add(event)

        await session.commit()

    # Build index
    response = await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": False},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] in {"success", "skipped"}
    assert body["chunk_count"] >= 0
    assert "index_version" in body
    assert "built_at" in body


@pytest.mark.asyncio
async def test_post_qa_ask_with_index_returns_answer(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ask with built index should return answer with sources."""
    # Create session with speech events and build index
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession
        from app.models.speech_event import SpeechEvent

        session_id = "test_session_qa_002"
        session_obj = LectureSession(
            id=session_id,
            user_id="test_user",
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
            qa_index_built=False,
        )
        session.add(session_obj)

        event = SpeechEvent(
            session_id=session_id,
            start_ms=0,
            end_ms=5000,
            text="機械学習は人工知能の一分野です",
            confidence=0.95,
            is_final=True,
            speaker="teacher",
        )
        session.add(event)
        await session.commit()

    build_response = await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": True},
        headers=AUTH_HEADERS,
    )
    assert build_response.status_code == 200

    # Ask question
    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": "機械学習とは何ですか",
            "lang_mode": "ja",
            "retrieval_mode": "source-only",
            "top_k": 5,
            "context_window": 1,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert "answer" in body
    assert "confidence" in body
    assert body["confidence"] in {"high", "medium", "low"}
    assert "sources" in body
    assert isinstance(body["sources"], list)
    assert len(body["sources"]) > 0
    assert "action_next" in body
    assert "verification_summary" in body


@pytest.mark.asyncio
async def test_post_qa_ask_without_index_returns_fallback(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ask without index should return fallback."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession

        session_id = "test_session_qa_003"
        session_obj = LectureSession(
            id=session_id,
            user_id="test_user",
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
            qa_index_built=False,
        )
        session.add(session_obj)
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": "テスト質問",
            "lang_mode": "ja",
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["confidence"] == "low"
    assert body["sources"] == []
    assert body["fallback"] is not None


@pytest.mark.asyncio
async def test_post_qa_ask_persists_qa_turn(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ask should persist QA turn to database."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession
        from app.models.speech_event import SpeechEvent

        session_id = "test_session_qa_004"
        session_obj = LectureSession(
            id=session_id,
            user_id="test_user",
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
            qa_index_built=True,
        )
        session.add(session_obj)

        event = SpeechEvent(
            session_id=session_id,
            start_ms=0,
            end_ms=5000,
            text="Test content",
            confidence=0.95,
            is_final=True,
            speaker="teacher",
        )
        session.add(event)
        await session.commit()

    question = "テスト質問"
    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": question,
            "lang_mode": "ja",
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200

    # Verify persistence
    async with session_factory() as session:
        result = await session.execute(
            select(QATurn).where(
                QATurn.session_id == session_id,
                QATurn.feature == "lecture_qa",
                QATurn.question == question,
            )
        )
        qa_turn = result.scalar_one_or_none()

    assert qa_turn is not None
    assert qa_turn.feature == "lecture_qa"
    assert qa_turn.verifier_supported is True
    assert qa_turn.latency_ms >= 0


@pytest.mark.asyncio
async def test_post_qa_followup_returns_resolved_query(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Followup should return answer with resolved query."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession
        from app.models.speech_event import SpeechEvent

        session_id = "test_session_qa_005"
        session_obj = LectureSession(
            id=session_id,
            user_id="test_user",
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
            qa_index_built=True,
        )
        session.add(session_obj)

        event = SpeechEvent(
            session_id=session_id,
            start_ms=0,
            end_ms=5000,
            text="Test content",
            confidence=0.95,
            is_final=True,
            speaker="teacher",
        )
        session.add(event)
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/qa/followup",
        json={
            "session_id": session_id,
            "question": "それについてはどうですか",
            "lang_mode": "ja",
            "history_turns": 3,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert "answer" in body
    assert "resolved_query" in body
    assert isinstance(body["resolved_query"], str)


@pytest.mark.asyncio
async def test_post_qa_ask_with_invalid_payload_returns_400(
    async_client: AsyncClient,
) -> None:
    """Validation failures should return 400 error response."""
    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": "  ",  # Blank session_id
            "question": "Test?",
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_post_qa_ask_with_invalid_lang_mode_returns_400(
    async_client: AsyncClient,
) -> None:
    """Invalid lang_mode should fail validation."""
    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": "test_session",
            "question": "Test?",
            "lang_mode": "fr",  # Invalid
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_post_qa_ask_without_lecture_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Lecture QA endpoint should reject requests without auth token."""
    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": "test_session",
            "question": "Test?",
            "lang_mode": "ja",
        },
        headers={USER_ID_HEADER: "test_user"},  # Missing lecture token
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_qa_ask_without_user_id_returns_401(
    async_client: AsyncClient,
) -> None:
    """Lecture QA endpoint should reject requests without user ID."""
    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": "test_session",
            "question": "Test?",
            "lang_mode": "ja",
        },
        headers={LECTURE_TOKEN_HEADER: settings.lecture_api_token},  # Missing user ID
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_qa_index_build_validates_session_ownership(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Index build should return 404 for session owned by another user."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession

        session_id = "test_session_qa_006"
        session_obj = LectureSession(
            id=session_id,
            user_id="other_user",  # Different user
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
            qa_index_built=False,
        )
        session.add(session_obj)
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": False},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_qa_ask_with_other_user_session_returns_404(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ask should return 404 for a session owned by another user."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession

        session_obj = LectureSession(
            id="test_session_qa_009",
            user_id="other_user",
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
        )
        session.add(session_obj)
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": "test_session_qa_009",
            "question": "テスト質問",
            "lang_mode": "ja",
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_qa_followup_with_other_user_session_returns_404(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Follow-up should return 404 for a session owned by another user."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession

        session_obj = LectureSession(
            id="test_session_qa_010",
            user_id="other_user",
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
        )
        session.add(session_obj)
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/qa/followup",
        json={
            "session_id": "test_session_qa_010",
            "question": "それについてはどうですか",
            "lang_mode": "ja",
            "history_turns": 3,
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_qa_ask_with_source_plus_context_mode(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ask with source-plus-context should return expanded sources."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession
        from app.models.speech_event import SpeechEvent

        session_id = "test_session_qa_007"
        session_obj = LectureSession(
            id=session_id,
            user_id="test_user",
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
            qa_index_built=True,
        )
        session.add(session_obj)

        # Add multiple speech events
        for i in range(5):
            event = SpeechEvent(
                session_id=session_id,
                start_ms=i * 10000,
                end_ms=(i + 1) * 10000,
                text=f"Test speech content {i + 1}",
                confidence=0.95,
                is_final=True,
                speaker="teacher",
            )
            session.add(event)
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": "テスト質問",
            "lang_mode": "ja",
            "retrieval_mode": "source-plus-context",
            "top_k": 3,
            "context_window": 1,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert "sources" in body
    # Context expansion may return more sources than top_k
    assert isinstance(body["sources"], list)


@pytest.mark.asyncio
async def test_post_qa_ask_respects_top_k_limit(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ask should respect top_k parameter."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession
        from app.models.speech_event import SpeechEvent

        session_id = "test_session_qa_008"
        session_obj = LectureSession(
            id=session_id,
            user_id="test_user",
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
            qa_index_built=True,
        )
        session.add(session_obj)

        # Add many speech events
        for i in range(10):
            event = SpeechEvent(
                session_id=session_id,
                start_ms=i * 10000,
                end_ms=(i + 1) * 10000,
                text=f"Test speech content {i + 1}",
                confidence=0.95,
                is_final=True,
                speaker="teacher",
            )
            session.add(event)
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": "テスト質問",
            "lang_mode": "ja",
            "top_k": 3,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    # Should return at most top_k sources (or fewer if no matches)
    assert len(body["sources"]) <= 3


def test_get_lecture_retrieval_service_uses_azure_when_enabled(
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

    service = lecture_qa_api.get_lecture_retrieval_service()
    assert isinstance(service, AzureSearchLectureRetrievalService)


def test_get_lecture_retrieval_service_falls_back_to_bm25_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieval provider should keep BM25 path when Azure is disabled."""
    monkeypatch.setattr(settings, "azure_search_enabled", False)
    monkeypatch.setattr(settings, "azure_search_endpoint", "")
    monkeypatch.setattr(settings, "azure_search_api_key", "")

    service = lecture_qa_api.get_lecture_retrieval_service()
    assert isinstance(service, BM25LectureRetrievalService)


@pytest.mark.asyncio
async def test_post_qa_index_build_uses_azure_service_when_enabled(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Index build endpoint should succeed via Azure index service wiring."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession
        from app.models.speech_event import SpeechEvent

        session_id = "test_session_qa_azure_001"
        session.add(
            LectureSession(
                id=session_id,
                user_id="test_user",
                course_name="Test Course",
                status="active",
                started_at=datetime.now(UTC),
                qa_index_built=False,
            )
        )
        session.add(
            SpeechEvent(
                session_id=session_id,
                start_ms=0,
                end_ms=5000,
                text="Azure index source",
                confidence=0.95,
                is_final=True,
                speaker="teacher",
            )
        )
        await session.commit()

    fake_search = FakeAzureSearchService()
    monkeypatch.setattr(settings, "azure_search_enabled", True)
    monkeypatch.setattr(settings, "azure_search_endpoint", "https://example.search")
    monkeypatch.setattr(settings, "azure_search_api_key", "dummy-key")
    monkeypatch.setattr(
        lecture_qa_api,
        "get_azure_search_service",
        lambda: fake_search,
    )

    response = await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": True},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert len(fake_search.upsert_calls) == 1


@pytest.mark.asyncio
async def test_post_qa_ask_uses_azure_retrieval_when_enabled(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ask endpoint should return sources from Azure retrieval adapter."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession

        session_id = "test_session_qa_azure_002"
        session.add(
            LectureSession(
                id=session_id,
                user_id="test_user",
                course_name="Test Course",
                status="active",
                started_at=datetime.now(UTC),
                qa_index_built=True,
            )
        )
        await session.commit()

    fake_search = FakeAzureSearchService(
        documents=[
            {
                "chunk_id": "azure-chunk-1",
                "chunk_type": "speech",
                "speech_text": "Azure retrieval text",
                "start_ms": 0,
                "end_ms": 5000,
                "@search.score": 2.0,
            }
        ]
    )
    monkeypatch.setattr(settings, "azure_search_enabled", True)
    monkeypatch.setattr(settings, "azure_search_endpoint", "https://example.search")
    monkeypatch.setattr(settings, "azure_search_api_key", "dummy-key")
    monkeypatch.setattr(
        lecture_qa_api,
        "get_azure_search_service",
        lambda: fake_search,
    )

    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": "Azure では何を説明しましたか",
            "lang_mode": "ja",
            "retrieval_mode": "source-only",
            "top_k": 3,
            "context_window": 1,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["sources"][0]["chunk_id"] == "azure-chunk-1"


@pytest.mark.asyncio
async def test_post_qa_index_build_returns_503_when_azure_partial_failure(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Index build should return 503 on partial Azure indexing failure."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_chunk import LectureChunk
        from app.models.lecture_session import LectureSession

        session_id = "test_session_qa_azure_003"
        session.add(
            LectureSession(
                id=session_id,
                user_id="test_user",
                course_name="Test Course",
                status="active",
                started_at=datetime.now(UTC),
                qa_index_built=False,
            )
        )
        session.add(
            LectureChunk(
                id="chunk-a",
                session_id=session_id,
                chunk_type="speech",
                start_ms=0,
                end_ms=5000,
                speech_text="A",
                visual_text=None,
                summary_text=None,
                keywords_json=[],
                embedding_text="A",
                indexed_to_search=False,
            )
        )
        session.add(
            LectureChunk(
                id="chunk-b",
                session_id=session_id,
                chunk_type="speech",
                start_ms=5000,
                end_ms=10000,
                speech_text="B",
                visual_text=None,
                summary_text=None,
                keywords_json=[],
                embedding_text="B",
                indexed_to_search=False,
            )
        )
        await session.commit()

    fake_search = FakeAzureSearchService(
        documents=[],
        succeeded_chunk_ids=["chunk-a"],
    )
    monkeypatch.setattr(settings, "azure_search_enabled", True)
    monkeypatch.setattr(settings, "azure_search_endpoint", "https://example.search")
    monkeypatch.setattr(settings, "azure_search_api_key", "dummy-key")
    monkeypatch.setattr(
        lecture_qa_api,
        "get_azure_search_service",
        lambda: fake_search,
    )

    response = await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": True},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_post_qa_ask_returns_503_when_azure_search_fails(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ask endpoint should return 503 when Azure search query fails."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession

        session_id = "test_session_qa_azure_004"
        session.add(
            LectureSession(
                id=session_id,
                user_id="test_user",
                course_name="Test Course",
                status="active",
                started_at=datetime.now(UTC),
                qa_index_built=True,
            )
        )
        await session.commit()

    fake_search = FakeAzureSearchService(documents=[], fail_search=True)
    monkeypatch.setattr(settings, "azure_search_enabled", True)
    monkeypatch.setattr(settings, "azure_search_endpoint", "https://example.search")
    monkeypatch.setattr(settings, "azure_search_api_key", "dummy-key")
    monkeypatch.setattr(
        lecture_qa_api,
        "get_azure_search_service",
        lambda: fake_search,
    )

    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": "error path",
            "lang_mode": "ja",
            "retrieval_mode": "source-only",
            "top_k": 3,
            "context_window": 1,
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 503

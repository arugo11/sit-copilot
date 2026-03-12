"""Integration tests for lecture QA API endpoints."""

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v4 import lecture_qa as lecture_qa_api
from app.core.auth import LECTURE_TOKEN_HEADER, USER_ID_HEADER
from app.core.config import settings
from app.main import app
from app.models.qa_turn import QATurn
from app.schemas.lecture_qa import LectureSource
from app.services.lecture_answerer_service import (
    LectureAnswerDraft,
    LectureAnswererError,
)
from app.services.lecture_retrieval_service import (
    BM25LectureRetrievalService,
    ResilientLectureRetrievalService,
)
from app.services.observability.weave_observer_service import NoopWeaveObserverService
from app.services.observed_lecture_answerer_service import (
    ObservedLectureAnswererService,
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


class StaticLectureRetriever:
    """Retriever test double returning preconfigured sources."""

    def __init__(self, sources: list[LectureSource]) -> None:
        self._sources = sources

    async def retrieve(
        self,
        session_id: str,
        query: str,
        mode: str,
        top_k: int,
        context_window: int,
    ) -> list[LectureSource]:
        _ = (session_id, query, mode, top_k, context_window)
        return self._sources


class ErrorLectureAnswerer:
    """Answerer test double that always raises LectureAnswererError."""

    async def answer(
        self,
        question: str,
        lang_mode: str,
        sources: list[LectureSource],
        history: str,
    ) -> LectureAnswerDraft:
        _ = (question, lang_mode, sources, history)
        raise LectureAnswererError("synthetic answerer failure")


@pytest.mark.asyncio
async def test_post_autotitle_log_writes_jsonl(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Auto-title debug endpoint should append one JSON line."""
    log_dir = tmp_path / ".log"
    log_path = log_dir / "auto-title-debug.log"
    monkeypatch.setattr(lecture_qa_api, "AUTO_TITLE_DEBUG_LOG_DIR", log_dir)
    monkeypatch.setattr(lecture_qa_api, "AUTO_TITLE_DEBUG_LOG_PATH", log_path)

    response = await async_client.post(
        "/api/v4/lecture/qa/autotitle/log",
        json={
            "session_id": "test_session_qa_debug",
            "event": "generate.response",
            "level": "warning",
            "locale": "ja",
            "payload": {
                "attempt": 1,
                "reason": "too_long",
            },
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "logged"
    assert body["log_file"] == ".log/auto-title-debug.log"
    assert log_path.exists()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["user_id"] == "test_user"
    assert record["session_id"] == "test_session_qa_debug"
    assert record["event"] == "generate.response"
    assert record["level"] == "warning"
    assert record["locale"] == "ja"
    assert record["payload"]["reason"] == "too_long"
    assert "timestamp" in record


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
async def test_post_qa_ask_returns_feature_disabled_when_env_flag_off(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QA ask should fail closed when the env kill switch is off."""
    monkeypatch.setattr(settings, "lecture_qa_enabled", False)

    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession

        session.add(
            LectureSession(
                id="test_session_qa_disabled_ask",
                user_id="test_user",
                course_name="Test Course",
                status="active",
                started_at=datetime.now(UTC),
                qa_index_built=False,
            )
        )
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": "test_session_qa_disabled_ask",
            "question": "機械学習とは何ですか？",
            "lang_mode": "ja",
            "retrieval_mode": "source-only",
            "top_k": 5,
            "context_window": 1,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["fallback"] == "feature_disabled"
    assert body["sources"] == []


@pytest.mark.asyncio
async def test_post_qa_followup_returns_feature_disabled_when_env_flag_off(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QA follow-up should fail closed when the env kill switch is off."""
    monkeypatch.setattr(settings, "lecture_qa_enabled", False)

    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession

        session.add(
            LectureSession(
                id="test_session_qa_disabled_followup",
                user_id="test_user",
                course_name="Test Course",
                status="active",
                started_at=datetime.now(UTC),
                qa_index_built=False,
            )
        )
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/qa/followup",
        json={
            "session_id": "test_session_qa_disabled_followup",
            "question": "それはなぜですか？",
            "lang_mode": "ja",
            "retrieval_mode": "source-only",
            "top_k": 5,
            "context_window": 1,
            "history_turns": 3,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["fallback"] == "feature_disabled"
    assert body["resolved_query"] == "それはなぜですか？"


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
async def test_post_qa_ask_answerer_error_without_grounded_source_includes_reason(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ask should include raw answerer reason when grounded snippet cannot be built."""
    async with session_factory() as session:
        from datetime import UTC, datetime

        from app.models.lecture_session import LectureSession

        session_id = "test_session_qa_reason_001"
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

    app.dependency_overrides[lecture_qa_api.get_lecture_retrieval_service] = lambda: (
        StaticLectureRetriever(
            [
                LectureSource(
                    chunk_id="speech_1",
                    type="speech",
                    text="   ",
                    bm25_score=5.0,
                )
            ]
        )
    )
    app.dependency_overrides[lecture_qa_api.get_lecture_answerer_service] = lambda: (
        ErrorLectureAnswerer()
    )

    try:
        response = await async_client.post(
            "/api/v4/lecture/qa/ask",
            json={
                "session_id": session_id,
                "question": "この内容を教えてください",
                "lang_mode": "ja",
                "retrieval_mode": "source-only",
                "top_k": 5,
                "context_window": 1,
            },
            headers=AUTH_HEADERS,
        )
    finally:
        app.dependency_overrides.pop(lecture_qa_api.get_lecture_retrieval_service, None)
        app.dependency_overrides.pop(lecture_qa_api.get_lecture_answerer_service, None)

    assert response.status_code == 200
    body = response.json()
    expected = "回答文生成に失敗しました。（理由: synthetic answerer failure）"
    assert body["answer"] == expected
    assert body["fallback"] == expected
    assert body["verification_summary"] == expected


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
    assert isinstance(service, ResilientLectureRetrievalService)


def test_get_lecture_retrieval_service_falls_back_to_bm25_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieval provider should keep BM25 path when Azure is disabled."""
    monkeypatch.setattr(settings, "azure_search_enabled", False)
    monkeypatch.setattr(settings, "azure_search_endpoint", "")
    monkeypatch.setattr(settings, "azure_search_api_key", "")

    service = lecture_qa_api.get_lecture_retrieval_service()
    assert isinstance(service, BM25LectureRetrievalService)


def test_get_shared_lecture_answerer_service_reuses_instance_for_same_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answerer provider should reuse process-shared instance for identical settings."""
    monkeypatch.setattr(lecture_qa_api, "_shared_lecture_answerer_service", None)
    monkeypatch.setattr(lecture_qa_api, "_shared_lecture_answerer_service_key", None)
    monkeypatch.setattr(settings, "azure_openai_api_key", "test-key")
    monkeypatch.setattr(
        settings, "azure_openai_endpoint", "https://example.openai.azure.com"
    )
    monkeypatch.setattr(settings, "azure_openai_account_name", "example")
    monkeypatch.setattr(settings, "azure_openai_model", "gpt-5-nano")
    monkeypatch.setattr(settings, "lecture_qa_answer_max_retries", 2)
    monkeypatch.setattr(settings, "lecture_qa_answer_retry_delay_seconds", 0.5)
    monkeypatch.setattr(settings, "lecture_qa_answer_min_request_interval_seconds", 0.1)
    monkeypatch.setattr(settings, "azure_openai_api_version", "2024-05-01-preview")

    first = lecture_qa_api.get_shared_lecture_answerer_service()
    second = lecture_qa_api.get_shared_lecture_answerer_service()

    assert first is second


def test_get_shared_lecture_answerer_service_recreates_when_config_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answerer provider should recreate shared instance after setting changes."""
    monkeypatch.setattr(lecture_qa_api, "_shared_lecture_answerer_service", None)
    monkeypatch.setattr(lecture_qa_api, "_shared_lecture_answerer_service_key", None)
    monkeypatch.setattr(settings, "azure_openai_api_key", "test-key")
    monkeypatch.setattr(
        settings, "azure_openai_endpoint", "https://example.openai.azure.com"
    )
    monkeypatch.setattr(settings, "azure_openai_account_name", "example")
    monkeypatch.setattr(settings, "azure_openai_model", "gpt-5-nano")
    monkeypatch.setattr(settings, "lecture_qa_answer_max_retries", 2)
    monkeypatch.setattr(settings, "lecture_qa_answer_retry_delay_seconds", 0.5)
    monkeypatch.setattr(settings, "lecture_qa_answer_min_request_interval_seconds", 0.1)
    monkeypatch.setattr(settings, "azure_openai_api_version", "2024-05-01-preview")

    first = lecture_qa_api.get_shared_lecture_answerer_service()
    monkeypatch.setattr(settings, "azure_openai_model", "gpt-5-mini")
    second = lecture_qa_api.get_shared_lecture_answerer_service()

    assert first is not second


def test_get_lecture_answerer_service_wraps_shared_inner_when_weave_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observed wrappers should be request-scoped while sharing the same inner answerer."""
    monkeypatch.setattr(lecture_qa_api, "_shared_lecture_answerer_service", None)
    monkeypatch.setattr(lecture_qa_api, "_shared_lecture_answerer_service_key", None)
    monkeypatch.setattr(settings.weave, "enabled", True)
    monkeypatch.setattr(settings, "azure_openai_api_key", "test-key")
    monkeypatch.setattr(
        settings, "azure_openai_endpoint", "https://example.openai.azure.com"
    )
    monkeypatch.setattr(settings, "azure_openai_account_name", "example")
    monkeypatch.setattr(settings, "azure_openai_model", "gpt-5-nano")
    monkeypatch.setattr(settings, "lecture_qa_answer_max_retries", 2)
    monkeypatch.setattr(settings, "lecture_qa_answer_retry_delay_seconds", 0.5)
    monkeypatch.setattr(settings, "lecture_qa_answer_min_request_interval_seconds", 0.1)
    monkeypatch.setattr(settings, "azure_openai_api_version", "2024-05-01-preview")

    observer = NoopWeaveObserverService()
    wrapped_a = lecture_qa_api.get_lecture_answerer_service(observer)
    wrapped_b = lecture_qa_api.get_lecture_answerer_service(observer)

    assert isinstance(wrapped_a, ObservedLectureAnswererService)
    assert isinstance(wrapped_b, ObservedLectureAnswererService)
    assert wrapped_a is not wrapped_b
    assert wrapped_a._inner is wrapped_b._inner


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
async def test_post_qa_index_build_falls_back_when_azure_partial_failure(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Index build should fallback to BM25 when Azure indexing partially fails."""
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

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"


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


# ============================================================================
# End-to-End Integration Tests (Actual API Flow)
# ============================================================================


@pytest.mark.asyncio
async def test_e2e_lecture_qa_full_workflow(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """End-to-end test: session start → speech events → index build → ask → followup.

    This test performs a complete QA workflow using actual HTTP API calls
    and verifies database persistence at each step.

    Flow:
    1. Start a lecture session via POST /lecture/session/start
    2. Add speech events via POST /lecture/speech/chunk
    3. Build QA index via POST /lecture/qa/index/build
    4. Ask a question via POST /lecture/qa/ask
    5. Ask a follow-up via POST /lecture/qa/followup
    6. Verify database persistence (QATurn records)
    """
    # Step 1: Start a lecture session
    start_payload = {
        "course_name": "データ構造とアルゴリズム",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=AUTH_HEADERS,
    )
    assert start_response.status_code == 200
    start_body = start_response.json()
    session_id = start_body["session_id"]
    assert session_id.startswith("lec_")

    # Verify session was persisted
    async with session_factory() as session:
        from app.models.lecture_session import LectureSession

        result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        lecture_session = result.scalar_one()
    assert lecture_session is not None
    assert lecture_session.user_id == "test_user"
    assert lecture_session.course_name == start_payload["course_name"]

    # Step 2: Add speech events (simulating live lecture transcription)
    speech_events = [
        {
            "session_id": session_id,
            "start_ms": 15000,
            "end_ms": 25000,
            "text": "今日はハッシュテーブルについて学習します。ハッシュテーブルはキーと値のペアを高速に検索するデータ構造です。",
            "confidence": 0.95,
            "is_final": True,
            "speaker": "teacher",
        },
        {
            "session_id": session_id,
            "start_ms": 26000,
            "end_ms": 36000,
            "text": "ハッシュ関数を使ってキーをインデックスに変換し、配列に値を格納します。平均的な検索時間はO(1)です。",
            "confidence": 0.93,
            "is_final": True,
            "speaker": "teacher",
        },
        {
            "session_id": session_id,
            "start_ms": 37000,
            "end_ms": 47000,
            "text": "ただし、ハッシュ衝突が発生する可能性があります。衝突回避にはチェイン法やオープンアドレス法が使われます。",
            "confidence": 0.94,
            "is_final": True,
            "speaker": "teacher",
        },
    ]

    event_ids = []
    for event_payload in speech_events:
        event_response = await async_client.post(
            "/api/v4/lecture/speech/chunk",
            json=event_payload,
            headers=AUTH_HEADERS,
        )
        assert event_response.status_code == 200
        event_body = event_response.json()
        assert event_body["accepted"] is True
        event_ids.append(event_body["event_id"])

    # Verify speech events were persisted
    async with session_factory() as session:
        from app.models.speech_event import SpeechEvent

        result = await session.execute(
            select(SpeechEvent)
            .where(SpeechEvent.session_id == session_id)
            .order_by(SpeechEvent.start_ms)
        )
        persisted_events = result.scalars().all()
    assert len(persisted_events) == len(speech_events)
    assert persisted_events[0].text.startswith("今日はハッシュテーブル")

    # Step 3: Build QA index
    index_build_response = await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": False},
        headers=AUTH_HEADERS,
    )
    assert index_build_response.status_code == 200
    index_body = index_build_response.json()
    assert index_body["status"] == "success"
    assert index_body["chunk_count"] >= len(speech_events)
    assert "index_version" in index_body

    # Verify qa_index_built flag was updated
    async with session_factory() as session:
        result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        updated_session = result.scalar_one()
    assert updated_session.qa_index_built is True

    # Step 4: Ask a question
    ask_payload = {
        "session_id": session_id,
        "question": "ハッシュテーブルの検索時間はどのくらいですか",
        "lang_mode": "ja",
        "retrieval_mode": "source-only",
        "top_k": 5,
        "context_window": 1,
    }
    ask_response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json=ask_payload,
        headers=AUTH_HEADERS,
    )
    assert ask_response.status_code == 200
    ask_body = ask_response.json()
    assert "answer" in ask_body
    assert ask_body["answer"] != ""
    assert ask_body["confidence"] in {"high", "medium", "low"}
    assert isinstance(ask_body["sources"], list)
    assert len(ask_body["sources"]) > 0  # Should have retrieved sources
    assert "action_next" in ask_body
    assert "verification_summary" in ask_body

    # Verify source content
    first_source = ask_body["sources"][0]
    assert "chunk_id" in first_source
    assert "text" in first_source
    assert "bm25_score" in first_source

    # Verify QATurn was persisted
    async with session_factory() as session:
        result = await session.execute(
            select(QATurn).where(
                QATurn.session_id == session_id,
                QATurn.question == ask_payload["question"],
            )
        )
        qa_turn = result.scalar_one()
    assert qa_turn is not None
    assert qa_turn.feature == "lecture_qa"
    assert qa_turn.answer == ask_body["answer"]
    assert qa_turn.confidence == ask_body["confidence"]
    assert qa_turn.verifier_supported is True
    assert qa_turn.latency_ms >= 0

    # Step 5: Ask a follow-up question
    followup_payload = {
        "session_id": session_id,
        "question": "衝突が起きたらどうなりますか",
        "lang_mode": "ja",
        "retrieval_mode": "source-only",
        "top_k": 5,
        "history_turns": 3,
    }
    followup_response = await async_client.post(
        "/api/v4/lecture/qa/followup",
        json=followup_payload,
        headers=AUTH_HEADERS,
    )
    assert followup_response.status_code == 200
    followup_body = followup_response.json()
    assert "answer" in followup_body
    assert followup_body["answer"] != ""
    assert "resolved_query" in followup_body
    assert isinstance(followup_body["resolved_query"], str)
    assert followup_body["resolved_query"] != ""
    assert len(followup_body["sources"]) > 0

    # Verify second QATurn was persisted
    async with session_factory() as session:
        result = await session.execute(
            select(QATurn).where(QATurn.session_id == session_id)
        )
        all_qa_turns = result.scalars().all()
    assert len(all_qa_turns) == 2  # One from ask, one from followup

    # Step 6: Verify retrieval found relevant content about hash collisions
    # The follow-up asked about "衝突" (collision), should retrieve event mentioning it
    sources_text = " ".join([s["text"] for s in followup_body["sources"]])
    assert "衝突" in sources_text or "collision" in sources_text.lower()


@pytest.mark.asyncio
async def test_e2e_lecture_qa_fallback_without_index(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """End-to-end test: QA ask without index should return fallback answer."""
    # Start session
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "テスト講義",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    # Ask without building index
    ask_response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": "何でも質問",
            "lang_mode": "ja",
        },
        headers=AUTH_HEADERS,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["confidence"] == "low"
    assert body["sources"] == []
    assert body["fallback"] is not None
    assert "見つかりません" in body["fallback"] or "ありません" in body["fallback"]


@pytest.mark.asyncio
async def test_e2e_lecture_qa_source_plus_context_mode(
    async_client: AsyncClient,
) -> None:
    """End-to-end test: source-plus-context mode should return expanded sources."""
    # Start session
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "テスト講義",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    # Add multiple speech events to test context expansion
    for i, text in enumerate(
        [
            "最初の概念を説明します。",
            "次に重要なポイントです。",
            "ここが検索対象の内容です。",
            "追加のコンテキスト情報。",
            "最後のまとめです。",
        ]
    ):
        await async_client.post(
            "/api/v4/lecture/speech/chunk",
            json={
                "session_id": session_id,
                "start_ms": i * 10000,
                "end_ms": (i + 1) * 10000,
                "text": text,
                "confidence": 0.95,
                "is_final": True,
                "speaker": "teacher",
            },
            headers=AUTH_HEADERS,
        )

    # Build index
    await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": True},
        headers=AUTH_HEADERS,
    )

    # Ask with source-plus-context mode
    ask_response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": "検索対象",
            "lang_mode": "ja",
            "retrieval_mode": "source-plus-context",
            "top_k": 1,
            "context_window": 1,
        },
        headers=AUTH_HEADERS,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    # Should return direct hit + context (up to 3 chunks with window=1)
    assert len(body["sources"]) >= 1
    # Check that at least one is a direct hit
    direct_hits = [s for s in body["sources"] if s["is_direct_hit"]]
    assert len(direct_hits) >= 1


@pytest.mark.asyncio
async def test_e2e_lecture_qa_rebuild_index(
    async_client: AsyncClient,
) -> None:
    """End-to-end test: index rebuild should update existing index."""
    # Start session and add events
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "テスト講義",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 0,
            "end_ms": 5000,
            "text": "最初のコンテンツ",
            "confidence": 0.95,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )

    # First build
    first_build = await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": False},
        headers=AUTH_HEADERS,
    )
    assert first_build.status_code == 200
    first_body = first_build.json()
    assert first_body["status"] == "success"
    assert first_body["chunk_count"] == 1

    # Add more events
    await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 6000,
            "end_ms": 11000,
            "text": "追加のコンテンツ",
            "confidence": 0.95,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )

    # Rebuild
    rebuild_response = await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": True},
        headers=AUTH_HEADERS,
    )
    assert rebuild_response.status_code == 200
    rebuild_body = rebuild_response.json()
    assert rebuild_body["status"] == "success"
    assert rebuild_body["chunk_count"] == 2


@pytest.mark.asyncio
async def test_e2e_lecture_qa_ownership_enforcement(
    async_client: AsyncClient,
) -> None:
    """End-to-end test: User cannot access another user's QA resources."""
    # User A starts session
    owner_a_headers = {
        LECTURE_TOKEN_HEADER: settings.lecture_api_token,
        USER_ID_HEADER: "owner_a",
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "オーナーAの講義",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=owner_a_headers,
    )
    session_id = start_response.json()["session_id"]

    # User B tries to build index for User A's session
    owner_b_headers = {
        LECTURE_TOKEN_HEADER: settings.lecture_api_token,
        USER_ID_HEADER: "owner_b",
    }
    build_response = await async_client.post(
        "/api/v4/lecture/qa/index/build",
        json={"session_id": session_id, "rebuild": False},
        headers=owner_b_headers,
    )
    assert build_response.status_code == 404

    # User B tries to ask question for User A's session
    ask_response = await async_client.post(
        "/api/v4/lecture/qa/ask",
        json={
            "session_id": session_id,
            "question": "質問",
            "lang_mode": "ja",
        },
        headers=owner_b_headers,
    )
    assert ask_response.status_code == 404

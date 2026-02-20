"""Unit tests for lecture index service implementations."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_chunk import LectureChunk
from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.services.lecture_index_service import AzureLectureIndexService


class FakeAzureSearchService:
    """Fake Azure Search service for deterministic unit tests."""

    def __init__(
        self,
        succeeded_chunk_ids: list[str] | None = None,
        has_session_documents: bool = False,
    ) -> None:
        self.succeeded_chunk_ids = succeeded_chunk_ids
        self._has_session_documents = has_session_documents
        self.upsert_calls: list[list[dict[str, object]]] = []

    async def ensure_lecture_index(self) -> None:
        """No-op for tests."""

    async def upsert_lecture_documents(
        self,
        documents: list[dict[str, object]],
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
    ) -> list[dict[str, object]]:
        _ = (search_text, session_id, top_k)
        return []

    async def list_session_documents(
        self,
        *,
        session_id: str,
        max_documents: int = 1000,
    ) -> list[dict[str, object]]:
        _ = (session_id, max_documents)
        return []

    async def has_session_documents(self, *, session_id: str) -> bool:
        _ = session_id
        return self._has_session_documents


async def _create_session(
    db_session: AsyncSession,
    *,
    session_id: str,
    user_id: str,
    qa_index_built: bool = False,
) -> LectureSession:
    session = LectureSession(
        id=session_id,
        user_id=user_id,
        course_name="Test Course",
        lang_mode="ja",
        status="active",
        started_at=datetime.now(UTC),
        qa_index_built=qa_index_built,
    )
    db_session.add(session)
    await db_session.flush()
    return session


@pytest.mark.asyncio
async def test_azure_build_index_from_lecture_chunks_updates_flags(
    db_session: AsyncSession,
) -> None:
    """Successful Azure indexing should set qa_index_built and chunk flags."""
    session = await _create_session(
        db_session,
        session_id="lec_azure_idx_001",
        user_id="user_1",
    )

    chunk_a = LectureChunk(
        id="chunk-a",
        session_id=session.id,
        chunk_type="speech",
        start_ms=0,
        end_ms=5000,
        speech_text="alpha",
        visual_text=None,
        summary_text=None,
        keywords_json=["alpha"],
        embedding_text="alpha",
        indexed_to_search=False,
    )
    chunk_b = LectureChunk(
        id="chunk-b",
        session_id=session.id,
        chunk_type="visual",
        start_ms=5000,
        end_ms=10000,
        speech_text=None,
        visual_text="beta",
        summary_text=None,
        keywords_json=["beta"],
        embedding_text="beta",
        indexed_to_search=False,
    )
    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    service = AzureLectureIndexService(
        db=db_session,
        search_service=FakeAzureSearchService(),
    )

    response = await service.build_index(
        session_id=session.id,
        user_id="user_1",
        rebuild=True,
    )

    assert response.status == "success"
    assert response.chunk_count == 2

    session_row = (
        await db_session.execute(
            select(LectureSession).where(LectureSession.id == session.id)
        )
    ).scalar_one()
    assert session_row.qa_index_built is True

    chunks = (
        (
            await db_session.execute(
                select(LectureChunk).where(LectureChunk.session_id == session.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(chunks) == 2
    assert all(chunk.indexed_to_search is True for chunk in chunks)


@pytest.mark.asyncio
async def test_azure_build_index_skips_when_already_built_without_rebuild(
    db_session: AsyncSession,
) -> None:
    """Index build should return skipped when already built and rebuild is false."""
    session = await _create_session(
        db_session,
        session_id="lec_azure_idx_002",
        user_id="user_1",
        qa_index_built=True,
    )
    fake_search = FakeAzureSearchService(has_session_documents=True)
    service = AzureLectureIndexService(db=db_session, search_service=fake_search)

    response = await service.build_index(
        session_id=session.id,
        user_id="user_1",
        rebuild=False,
    )

    assert response.status == "skipped"
    assert response.chunk_count == 0
    assert fake_search.upsert_calls == []


@pytest.mark.asyncio
async def test_azure_build_index_rebuilds_when_local_flag_true_but_remote_missing(
    db_session: AsyncSession,
) -> None:
    """Build should not skip when qa_index_built is true but Azure has no docs."""
    session = await _create_session(
        db_session,
        session_id="lec_azure_idx_005",
        user_id="user_1",
        qa_index_built=True,
    )
    db_session.add(
        SpeechEvent(
            id="speech-event-5",
            session_id=session.id,
            start_ms=0,
            end_ms=5000,
            text="missing remote docs",
            confidence=0.95,
            is_final=True,
            speaker="teacher",
        )
    )
    await db_session.flush()

    fake_search = FakeAzureSearchService(has_session_documents=False)
    service = AzureLectureIndexService(db=db_session, search_service=fake_search)

    response = await service.build_index(
        session_id=session.id,
        user_id="user_1",
        rebuild=False,
    )

    assert response.status == "success"
    assert response.chunk_count == 1
    assert len(fake_search.upsert_calls) == 1


@pytest.mark.asyncio
async def test_azure_build_index_raises_on_partial_indexing_failure(
    db_session: AsyncSession,
) -> None:
    """Partial Azure upsert result should raise and not set flags."""
    session = await _create_session(
        db_session,
        session_id="lec_azure_idx_003",
        user_id="user_1",
    )

    chunk_a = LectureChunk(
        id="chunk-a",
        session_id=session.id,
        chunk_type="speech",
        start_ms=0,
        end_ms=5000,
        speech_text="alpha",
        visual_text=None,
        summary_text=None,
        keywords_json=["alpha"],
        embedding_text="alpha",
        indexed_to_search=False,
    )
    chunk_b = LectureChunk(
        id="chunk-b",
        session_id=session.id,
        chunk_type="speech",
        start_ms=5000,
        end_ms=10000,
        speech_text="beta",
        visual_text=None,
        summary_text=None,
        keywords_json=["beta"],
        embedding_text="beta",
        indexed_to_search=False,
    )
    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    service = AzureLectureIndexService(
        db=db_session,
        search_service=FakeAzureSearchService(succeeded_chunk_ids=["chunk-a"]),
    )

    with pytest.raises(RuntimeError, match="indexing failed"):
        await service.build_index(
            session_id=session.id,
            user_id="user_1",
            rebuild=True,
        )

    chunks = (
        (
            await db_session.execute(
                select(LectureChunk).where(LectureChunk.session_id == session.id)
            )
        )
        .scalars()
        .all()
    )
    assert all(chunk.indexed_to_search is False for chunk in chunks)


@pytest.mark.asyncio
async def test_azure_build_index_uses_speech_events_when_chunks_absent(
    db_session: AsyncSession,
) -> None:
    """Index build should fallback to finalized speech events when chunks are absent."""
    session = await _create_session(
        db_session,
        session_id="lec_azure_idx_004",
        user_id="user_1",
    )

    event = SpeechEvent(
        id="speech-event-1",
        session_id=session.id,
        start_ms=0,
        end_ms=5000,
        text="speech fallback",
        confidence=0.95,
        is_final=True,
        speaker="teacher",
    )
    db_session.add(event)
    await db_session.flush()

    fake_search = FakeAzureSearchService(succeeded_chunk_ids=["speech-event-1"])
    service = AzureLectureIndexService(
        db=db_session,
        search_service=fake_search,
    )

    response = await service.build_index(
        session_id=session.id,
        user_id="user_1",
        rebuild=True,
    )

    assert response.status == "success"
    assert response.chunk_count == 1
    assert len(fake_search.upsert_calls) == 1
    assert fake_search.upsert_calls[0][0]["chunk_id"] == "speech-event-1"

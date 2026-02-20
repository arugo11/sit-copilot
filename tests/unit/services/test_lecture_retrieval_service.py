"""Unit tests for lecture retrieval service implementations."""

import pytest

from app.services.lecture_retrieval_service import AzureSearchLectureRetrievalService


class FakeAzureSearchService:
    """Fake Azure Search service for retrieval tests."""

    def __init__(self, documents: list[dict[str, object]]) -> None:
        self.documents = documents
        self.calls: list[dict[str, object]] = []

    async def ensure_lecture_index(self) -> None:
        """No-op for tests."""

    async def upsert_lecture_documents(
        self,
        documents: list[dict[str, object]],
    ) -> list[str]:
        _ = documents
        return []

    async def search_lecture_documents(
        self,
        *,
        search_text: str,
        session_id: str,
        top_k: int,
    ) -> list[dict[str, object]]:
        self.calls.append(
            {
                "search_text": search_text,
                "session_id": session_id,
                "top_k": top_k,
            }
        )
        return self.documents

    async def list_session_documents(
        self,
        *,
        session_id: str,
        max_documents: int = 1000,
    ) -> list[dict[str, object]]:
        _ = (session_id, max_documents)
        return self.documents

    async def has_session_documents(self, *, session_id: str) -> bool:
        _ = session_id
        return bool(self.documents)


@pytest.mark.asyncio
async def test_azure_retrieval_maps_documents_to_sources() -> None:
    """Azure documents should map to LectureSource payloads."""
    service = AzureSearchLectureRetrievalService(
        search_service=FakeAzureSearchService(
            documents=[
                {
                    "chunk_id": "chunk-1",
                    "chunk_type": "speech",
                    "speech_text": "機械学習の説明",
                    "start_ms": 62000,
                    "end_ms": 68000,
                    "speaker": "teacher",
                    "@search.score": 3.25,
                },
                {
                    "chunk_id": "chunk-2",
                    "chunk_type": "visual",
                    "visual_text": "勾配降下法",
                    "start_ms": 70000,
                    "end_ms": 70000,
                    "@search.score": 2.1,
                },
            ]
        )
    )

    sources = await service.retrieve(
        session_id="session-1",
        query="機械学習とは",
        mode="source-only",
        top_k=5,
        context_window=1,
    )

    assert len(sources) == 2
    assert sources[0].chunk_id == "chunk-1"
    assert sources[0].type == "speech"
    assert sources[0].timestamp == "01:02"
    assert sources[0].speaker == "teacher"
    assert sources[0].bm25_score == 3.25

    assert sources[1].chunk_id == "chunk-2"
    assert sources[1].type == "visual"
    assert sources[1].text == "勾配降下法"


@pytest.mark.asyncio
async def test_azure_retrieval_respects_top_k_and_skips_invalid_docs() -> None:
    """Retrieval should drop invalid docs and apply top_k limit."""
    fake = FakeAzureSearchService(
        documents=[
            {
                "chunk_id": "",
                "chunk_type": "speech",
                "speech_text": "invalid",
                "@search.score": 10,
            },
            {
                "chunk_id": "chunk-merged",
                "chunk_type": "merged",
                "summary_text": "要約テキスト",
                "start_ms": 1000,
                "@search.score": 5,
            },
            {
                "chunk_id": "chunk-visual",
                "chunk_type": "visual",
                "visual_text": "図表",
                "start_ms": 2000,
                "@search.score": 4,
            },
        ]
    )
    service = AzureSearchLectureRetrievalService(search_service=fake)

    sources = await service.retrieve(
        session_id="session-2",
        query="test",
        mode="source-plus-context",
        top_k=1,
        context_window=2,
    )

    assert len(sources) == 2
    assert sources[0].chunk_id == "chunk-merged"
    assert sources[0].type == "speech"  # merged maps to speech-compatible source
    assert sources[1].chunk_id == "chunk-visual"
    assert sources[1].is_direct_hit is False
    assert fake.calls[0]["session_id"] == "session-2"
    assert fake.calls[0]["top_k"] == 1


@pytest.mark.asyncio
async def test_azure_retrieval_expands_context_for_source_plus_context() -> None:
    """source-plus-context should include timeline neighbors."""
    fake = FakeAzureSearchService(
        documents=[
            {
                "chunk_id": "chunk-1",
                "chunk_type": "speech",
                "speech_text": "A",
                "start_ms": 1000,
                "@search.score": 10,
            },
            {
                "chunk_id": "chunk-2",
                "chunk_type": "speech",
                "speech_text": "B",
                "start_ms": 2000,
                "@search.score": 9,
            },
            {
                "chunk_id": "chunk-3",
                "chunk_type": "speech",
                "speech_text": "C",
                "start_ms": 3000,
                "@search.score": 8,
            },
        ]
    )
    service = AzureSearchLectureRetrievalService(search_service=fake)

    sources = await service.retrieve(
        session_id="session-ctx",
        query="A",
        mode="source-plus-context",
        top_k=1,
        context_window=1,
    )

    assert [source.chunk_id for source in sources] == ["chunk-1", "chunk-2"]
    assert sources[0].is_direct_hit is True
    assert sources[1].is_direct_hit is False


@pytest.mark.asyncio
async def test_azure_retrieval_reports_no_local_index() -> None:
    """Azure retrieval adapter should not expose local BM25 index methods."""
    service = AzureSearchLectureRetrievalService(
        search_service=FakeAzureSearchService(documents=[])
    )

    assert await service.get_index("session-3") is None
    assert await service.has_index("session-3") is False

    # No-op methods should not raise
    await service.set_index("session-3", index=None)  # type: ignore[arg-type]
    await service.remove_index("session-3")

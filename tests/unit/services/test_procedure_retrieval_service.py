"""Unit tests for procedure retrieval service implementations."""

import pytest

from app.services.procedure_retrieval_service import (
    AzureSearchProcedureRetrievalService,
)


class FakeProcedureSearchService:
    """Fake search backend for procedure retrieval tests."""

    def __init__(
        self,
        *,
        documents: list[dict[str, object]] | None = None,
        should_fail: bool = False,
    ) -> None:
        self._documents = documents or []
        self._should_fail = should_fail

    async def search_documents(
        self,
        *,
        query: str,
        top_k: int,
    ) -> list[dict[str, object]]:
        _ = (query, top_k)
        if self._should_fail:
            raise RuntimeError("search failed")
        return self._documents


@pytest.mark.asyncio
async def test_retrieve_maps_documents_to_procedure_sources() -> None:
    """Retriever should map Azure document fields to ProcedureSource."""
    service = AzureSearchProcedureRetrievalService(
        search_service=FakeProcedureSearchService(
            documents=[
                {
                    "source_id": "doc_001",
                    "title": "履修登録案内",
                    "section": "申請方法",
                    "snippet": "履修登録はポータルから行います。",
                }
            ]
        )
    )

    sources = await service.retrieve(
        query="履修登録",
        lang_mode="ja",
        limit=3,
    )

    assert len(sources) == 1
    assert sources[0].source_id == "doc_001"
    assert sources[0].title == "履修登録案内"
    assert sources[0].section == "申請方法"
    assert sources[0].snippet == "履修登録はポータルから行います。"


@pytest.mark.asyncio
async def test_retrieve_uses_fallback_keys_and_skips_invalid_documents() -> None:
    """Retriever should use key fallback chain and drop invalid docs."""
    service = AzureSearchProcedureRetrievalService(
        search_service=FakeProcedureSearchService(
            documents=[
                {
                    "id": "doc_002",
                    "name": "証明書発行案内",
                    "content": "証明書発行機で申請できます。",
                },
                {
                    "source_id": "",
                    "title": "invalid",
                    "snippet": "missing source id",
                },
            ]
        )
    )

    sources = await service.retrieve(
        query="証明書",
        lang_mode="ja",
        limit=3,
    )

    assert len(sources) == 1
    assert sources[0].source_id == "doc_002"
    assert sources[0].title == "証明書発行案内"
    assert sources[0].section == "本文"
    assert sources[0].snippet == "証明書発行機で申請できます。"


@pytest.mark.asyncio
async def test_retrieve_returns_empty_sources_when_search_backend_fails() -> None:
    """Search failures should return empty sources for safe fallback."""
    service = AzureSearchProcedureRetrievalService(
        search_service=FakeProcedureSearchService(should_fail=True)
    )

    sources = await service.retrieve(
        query="履修登録",
        lang_mode="ja",
        limit=3,
    )

    assert sources == []

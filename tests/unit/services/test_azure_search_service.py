"""Unit tests for Azure AI Search service internals."""

from __future__ import annotations

import pytest
from azure.core.exceptions import HttpResponseError

from app.services.azure_search_service import AzureAISearchService


class _FakeIndexClient:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.index = None

    async def __aenter__(self) -> "_FakeIndexClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    async def create_or_update_index(self, index) -> None:  # noqa: ANN001
        if self._error is not None:
            raise self._error

    async def get_index(self, index_name: str):  # noqa: ANN001
        _ = index_name
        return self.index


class _FakeField:
    def __init__(self, name: str, field_type: str) -> None:
        self.name = name
        self.type = field_type


class _FakeIndex:
    def __init__(self, fields: list[_FakeField]) -> None:
        self.fields = fields


@pytest.mark.asyncio
async def test_ensure_lecture_index_accepts_existing_field_change_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AzureAISearchService(
        endpoint="https://example.search.windows.net",
        api_key="test-key",
        index_name="lecture_index",
    )
    error = HttpResponseError(
        message="(OperationNotAllowed) Existing field 'keywords' cannot be changed."
    )

    fake_client = _FakeIndexClient(error)
    fake_client.index = _FakeIndex([_FakeField("keywords", "Edm.String")])

    monkeypatch.setattr(
        "azure.search.documents.indexes.aio.SearchIndexClient",
        lambda endpoint, credential: fake_client,  # noqa: ARG005
    )

    await service.ensure_lecture_index()

    assert service._index_ready is True
    assert service._keywords_field_is_collection is False


def test_normalize_documents_for_upload_converts_keywords_when_scalar_schema() -> None:
    service = AzureAISearchService(
        endpoint="https://example.search.windows.net",
        api_key="test-key",
        index_name="lecture_index",
    )
    service._keywords_field_is_collection = False

    normalized = service._normalize_documents_for_upload(
        [
            {
                "chunk_id": "chunk-1",
                "keywords": ["transformer", "attention", ""],
            }
        ]
    )

    assert normalized == [
        {
            "chunk_id": "chunk-1",
            "keywords": "transformer attention",
        }
    ]

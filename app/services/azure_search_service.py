"""Azure AI Search adapter for lecture index lifecycle and queries."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

__all__ = [
    "AzureSearchService",
    "AzureAISearchService",
    "get_shared_azure_search_service",
]


class AzureSearchService(Protocol):
    """Interface for lecture-oriented Azure AI Search operations."""

    async def ensure_lecture_index(self) -> None:
        """Create or update lecture index schema idempotently."""
        ...

    async def upsert_lecture_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> list[str]:
        """Upsert lecture documents and return succeeded chunk IDs."""
        ...

    async def search_lecture_documents(
        self,
        *,
        search_text: str,
        session_id: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Search lecture documents by query text within a session."""
        ...

    async def list_session_documents(
        self,
        *,
        session_id: str,
        max_documents: int = 1000,
    ) -> list[dict[str, Any]]:
        """List session documents ordered by timeline for context expansion."""
        ...

    async def has_session_documents(self, *, session_id: str) -> bool:
        """Return whether lecture index contains any docs for the session."""
        ...


class AzureAISearchService:
    """Azure AI Search implementation for lecture indexing and retrieval."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        index_name: str,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._index_name = index_name
        self._index_ready = False
        self._index_lock = asyncio.Lock()

    async def ensure_lecture_index(self) -> None:
        """Ensure `lecture_index` schema exists."""
        if self._index_ready:
            return

        async with self._index_lock:
            if self._index_ready:
                return

            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents.indexes.aio import SearchIndexClient

            credential = AzureKeyCredential(self._api_key)
            async with SearchIndexClient(
                endpoint=self._endpoint,
                credential=credential,
            ) as index_client:
                await index_client.create_or_update_index(self._build_index_schema())

            self._index_ready = True

    async def upsert_lecture_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> list[str]:
        """Upsert lecture documents with merge-or-upload semantics."""
        if not documents:
            return []

        await self.ensure_lecture_index()

        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents.aio import SearchClient

        credential = AzureKeyCredential(self._api_key)
        async with SearchClient(
            endpoint=self._endpoint,
            index_name=self._index_name,
            credential=credential,
        ) as search_client:
            results = await search_client.merge_or_upload_documents(documents)

        succeeded_chunk_ids: list[str] = []
        for result, document in zip(results, documents, strict=False):
            if getattr(result, "succeeded", False):
                chunk_id = str(document.get("chunk_id", "")).strip()
                if chunk_id:
                    succeeded_chunk_ids.append(chunk_id)

        return succeeded_chunk_ids

    async def search_lecture_documents(
        self,
        *,
        search_text: str,
        session_id: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Run session-scoped keyword search for lecture QA retrieval."""
        from azure.core.credentials import AzureKeyCredential
        from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
        from azure.search.documents.aio import SearchClient

        try:
            query = search_text.strip() or "*"
            top = max(1, top_k)
            credential = AzureKeyCredential(self._api_key)
            async with SearchClient(
                endpoint=self._endpoint,
                index_name=self._index_name,
                credential=credential,
            ) as search_client:
                results = await search_client.search(
                    search_text=query,
                    filter=self._build_session_filter(session_id),
                    top=top,
                )

                documents: list[dict[str, Any]] = []
                async for row in results:
                    documents.append(dict(row))
            return documents
        except ResourceNotFoundError:
            return []
        except HttpResponseError as exc:
            if exc.status_code == 404:
                return []
            raise

    async def list_session_documents(
        self,
        *,
        session_id: str,
        max_documents: int = 1000,
    ) -> list[dict[str, Any]]:
        """List session documents in timeline order."""
        from azure.core.credentials import AzureKeyCredential
        from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
        from azure.search.documents.aio import SearchClient

        try:
            credential = AzureKeyCredential(self._api_key)
            async with SearchClient(
                endpoint=self._endpoint,
                index_name=self._index_name,
                credential=credential,
            ) as search_client:
                results = await search_client.search(
                    search_text="*",
                    filter=self._build_session_filter(session_id),
                    order_by=["start_ms asc"],
                    top=max(1, max_documents),
                )

                documents: list[dict[str, Any]] = []
                async for row in results:
                    documents.append(dict(row))
            return documents
        except ResourceNotFoundError:
            return []
        except HttpResponseError as exc:
            if exc.status_code == 404:
                return []
            raise

    async def has_session_documents(self, *, session_id: str) -> bool:
        """Check whether any docs exist for the given session."""
        documents = await self.search_lecture_documents(
            search_text="*",
            session_id=session_id,
            top_k=1,
        )
        return bool(documents)

    def _build_index_schema(self) -> Any:
        """Build Azure Search index schema for lecture chunks."""
        from azure.search.documents.indexes.models import (
            SearchableField,
            SearchFieldDataType,
            SearchIndex,
            SimpleField,
        )

        string_type = SearchFieldDataType.String
        collection_string = SearchFieldDataType.Collection(string_type)

        return SearchIndex(
            name=self._index_name,
            fields=[
                SimpleField(
                    name="chunk_id",
                    type=string_type,
                    key=True,
                    filterable=True,
                ),
                SimpleField(
                    name="session_id",
                    type=string_type,
                    filterable=True,
                ),
                SearchableField(
                    name="course_name",
                    type=string_type,
                    filterable=True,
                ),
                SimpleField(
                    name="date",
                    type=string_type,
                    filterable=True,
                ),
                SimpleField(
                    name="chunk_type",
                    type=string_type,
                    filterable=True,
                ),
                SimpleField(
                    name="start_ms",
                    type=SearchFieldDataType.Int32,
                    filterable=True,
                    sortable=True,
                ),
                SimpleField(
                    name="end_ms",
                    type=SearchFieldDataType.Int32,
                    filterable=True,
                    sortable=True,
                ),
                SearchableField(name="speech_text", type=string_type),
                SearchableField(name="visual_text", type=string_type),
                SearchableField(name="summary_text", type=string_type),
                SearchableField(
                    name="keywords",
                    type=string_type,
                ),
                SimpleField(
                    name="lang",
                    type=string_type,
                    filterable=True,
                ),
                SimpleField(
                    name="speaker",
                    type=string_type,
                    filterable=True,
                ),
            ],
        )

    @staticmethod
    def _build_session_filter(session_id: str) -> str:
        escaped_session = session_id.replace("'", "''")
        return (
            f"session_id eq '{escaped_session}' and "
            "(chunk_type eq 'speech' or chunk_type eq 'visual' or chunk_type eq 'merged')"
        )


_shared_azure_search_service: AzureAISearchService | None = None
_shared_azure_search_service_key: tuple[str, str, str] | None = None


def get_shared_azure_search_service(
    *,
    endpoint: str,
    api_key: str,
    index_name: str,
) -> AzureAISearchService:
    """Return process-shared Azure Search service for stable schema cache."""
    global _shared_azure_search_service
    global _shared_azure_search_service_key

    key = (endpoint, api_key, index_name)
    if _shared_azure_search_service is None or _shared_azure_search_service_key != key:
        _shared_azure_search_service = AzureAISearchService(
            endpoint=endpoint,
            api_key=api_key,
            index_name=index_name,
        )
        _shared_azure_search_service_key = key

    return _shared_azure_search_service

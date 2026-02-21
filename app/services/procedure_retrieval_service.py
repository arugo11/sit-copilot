"""Procedure retrieval services backed by Azure Search."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from app.schemas.procedure import ProcedureSource

__all__ = [
    "ProcedureRetrievalService",
    "ProcedureSearchService",
    "AzureProcedureSearchService",
    "AzureSearchProcedureRetrievalService",
    "NoopProcedureRetrievalService",
]


class ProcedureRetrievalService(Protocol):
    """Interface for retrieving procedure evidence sources."""

    async def retrieve(
        self, query: str, lang_mode: str, limit: int = 3
    ) -> list[ProcedureSource]:
        """Retrieve source documents relevant to the procedure query."""
        ...


class ProcedureSearchService(Protocol):
    """Interface for procedure search backend."""

    async def search_documents(
        self,
        *,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Search procedure documents."""
        ...


class AzureProcedureSearchService:
    """Azure Search adapter for procedure document search."""

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

    async def search_documents(
        self,
        *,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Search procedure documents from Azure Search index."""
        from azure.search.documents import SearchClient

        credential = AzureKeyCredential(self._api_key)
        normalized_query = query.strip() or "*"

        def _run_search() -> list[dict[str, Any]]:
            search_client = SearchClient(
                endpoint=self._endpoint,
                index_name=self._index_name,
                credential=credential,
            )
            results = search_client.search(
                search_text=normalized_query,
                top=max(1, top_k),
            )
            return [dict(row) for row in results]

        try:
            return await asyncio.to_thread(_run_search)
        except ResourceNotFoundError:
            return []
        except HttpResponseError as exc:
            if exc.status_code == 404:
                return []
            raise


class AzureSearchProcedureRetrievalService:
    """Procedure retrieval service using Azure Search backend."""

    def __init__(self, search_service: ProcedureSearchService) -> None:
        self._search_service = search_service

    async def retrieve(
        self,
        query: str,
        lang_mode: str,
        limit: int = 3,
    ) -> list[ProcedureSource]:
        """Retrieve and map Azure documents into ProcedureSource payloads."""
        _ = lang_mode
        normalized_limit = max(1, limit)

        try:
            documents = await self._search_service.search_documents(
                query=query,
                top_k=normalized_limit,
            )
        except Exception:
            return []

        sources = self._to_sources(documents)
        return sources[:normalized_limit]

    @classmethod
    def _to_sources(cls, documents: list[dict[str, Any]]) -> list[ProcedureSource]:
        sources: list[ProcedureSource] = []
        for document in documents:
            source_id = cls._first_non_empty(
                document,
                "source_id",
                "chunk_id",
                "id",
            )
            title = cls._first_non_empty(
                document,
                "title",
                "doc_title",
                "source_title",
                "name",
            )
            section = cls._first_non_empty(
                document,
                "section",
                "heading",
                "chapter",
                "category",
            )
            snippet = cls._first_non_empty(
                document,
                "snippet",
                "content",
                "text",
                "body",
                "summary_text",
            )
            if not source_id or not title or not snippet:
                continue

            sources.append(
                ProcedureSource(
                    title=title,
                    section=section or "本文",
                    snippet=snippet,
                    source_id=source_id,
                )
            )
        return sources

    @staticmethod
    def _first_non_empty(document: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = document.get(key)
            if value is None:
                continue
            normalized = str(value).strip()
            if normalized:
                return normalized
        return ""


class NoopProcedureRetrievalService:
    """Deterministic no-source retriever used when Azure Search is unavailable."""

    async def retrieve(
        self,
        query: str,
        lang_mode: str,
        limit: int = 3,
    ) -> list[ProcedureSource]:
        _ = (query, lang_mode, limit)
        return []

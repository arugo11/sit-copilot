"""Lecture retrieval service using BM25 and Azure Search."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from rank_bm25 import BM25Okapi

from app.schemas.lecture_qa import LectureSource, RetrievalMode
from app.services.azure_search_service import AzureSearchService

__all__ = [
    "LectureRetrievalService",
    "BM25LectureRetrievalService",
    "AzureSearchLectureRetrievalService",
    "ResilientLectureRetrievalService",
    "BM25TokenCache",
    "LectureRetrievalIndex",
    "get_shared_lecture_retrieval_service",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BM25TokenCache:
    """Immutable cache for tokenized corpus to avoid re-tokenization."""

    tokenized_corpus: list[list[str]]
    chunk_ids: list[str]
    chunks: list[dict]

    def __len__(self) -> int:
        return len(self.chunk_ids)


@dataclass
class LectureRetrievalIndex:
    """BM25 index with metadata for lecture retrieval."""

    bm25: BM25Okapi
    cache: BM25TokenCache
    k1: float
    b: float

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        """Get BM25 scores for all documents."""
        return self.bm25.get_scores(query_tokens)


class LectureRetrievalService(Protocol):
    """Interface for retrieving lecture content using BM25."""

    async def retrieve(
        self,
        session_id: str,
        query: str,
        mode: RetrievalMode,
        top_k: int,
        context_window: int,
    ) -> list[LectureSource]:
        """Retrieve relevant lecture chunks with BM25 scoring."""
        ...

    async def get_index(self, session_id: str) -> LectureRetrievalIndex | None:
        """Get the BM25 index for a session."""
        ...

    async def set_index(self, session_id: str, index: LectureRetrievalIndex) -> None:
        """Store the BM25 index for a session."""
        ...

    async def has_index(self, session_id: str) -> bool:
        """Check if an index exists for a session."""
        ...

    async def remove_index(self, session_id: str) -> None:
        """Remove the index for a session."""
        ...


class BM25LectureRetrievalService:
    """BM25-based retrieval service with in-memory index caching."""

    DEFAULT_K1 = 1.2
    DEFAULT_B = 0.5
    DEFAULT_TOP_K = 5

    def __init__(
        self,
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
    ) -> None:
        """Initialize the BM25 retrieval service.

        Args:
            k1: Term frequency saturation parameter (1.2-1.5 for Japanese)
            b: Length normalization parameter (0.5-0.75 for lecture content)
        """
        self._k1 = k1
        self._b = b
        self._indexes: dict[str, LectureRetrievalIndex] = {}

    async def retrieve(
        self,
        session_id: str,
        query: str,
        mode: RetrievalMode,
        top_k: int,
        context_window: int,
    ) -> list[LectureSource]:
        """Retrieve relevant lecture chunks using BM25 search.

        Args:
            session_id: Lecture session identifier
            query: Search query text
            mode: Retrieval mode (source-only or source-plus-context)
            top_k: Maximum number of direct hits to return
            context_window: Number of neighboring chunks to include

        Returns:
            List of LectureSource with BM25 scores
        """
        index = await self.get_index(session_id)
        if index is None:
            return []

        # Tokenize query and run BM25 search in thread pool
        query_tokens = self._tokenize(query)
        scores = await asyncio.to_thread(index.get_scores, query_tokens)

        # Get top-k indices by score
        top_indices = self._get_top_k_indices(scores, top_k)

        # Build sources from indices
        sources = self._build_sources(
            index=index,
            indices=top_indices,
            scores=scores,
            is_direct_hit=True,
        )

        # Expand context if requested
        if mode == "source-plus-context" and context_window > 0:
            sources = self._expand_context(
                index=index,
                direct_sources=sources,
                scores=scores,
                context_window=context_window,
            )

        return sources

    async def get_index(self, session_id: str) -> LectureRetrievalIndex | None:
        """Get the BM25 index for a session."""
        return self._indexes.get(session_id)

    async def set_index(self, session_id: str, index: LectureRetrievalIndex) -> None:
        """Store the BM25 index for a session."""
        self._indexes[session_id] = index

    async def has_index(self, session_id: str) -> bool:
        """Check if an index exists for a session."""
        return session_id in self._indexes

    async def remove_index(self, session_id: str) -> None:
        """Remove the index for a session."""
        self._indexes.pop(session_id, None)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text for BM25 indexing.

        Uses simple whitespace tokenization with lowercasing.
        For production, consider integrating SudachiPy for Japanese.
        """
        return text.lower().split()

    def _get_top_k_indices(self, scores: list[float], k: int) -> list[int]:
        """Get indices of top-k scores.

        Args:
            scores: List of BM25 scores
            k: Number of top results to return

        Returns:
            List of indices sorted by score (descending)
        """
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in indexed_scores[:k]]

    def _build_sources(
        self,
        index: LectureRetrievalIndex,
        indices: list[int],
        scores: list[float],
        is_direct_hit: bool,
    ) -> list[LectureSource]:
        """Build LectureSource objects from chunk indices.

        Args:
            index: BM25 index with chunk metadata
            indices: Chunk indices to include
            scores: BM25 scores for all chunks
            is_direct_hit: Whether these are direct BM25 matches

        Returns:
            List of LectureSource objects
        """
        sources = []
        for idx in indices:
            chunk = index.cache.chunks[idx]
            source = LectureSource(
                chunk_id=chunk["id"],
                type=chunk["type"],
                text=chunk["text"],
                timestamp=chunk.get("timestamp"),
                start_ms=chunk.get("start_ms"),
                end_ms=chunk.get("end_ms"),
                speaker=chunk.get("speaker"),
                bm25_score=scores[idx],
                is_direct_hit=is_direct_hit,
            )
            sources.append(source)
        return sources

    def _expand_context(
        self,
        index: LectureRetrievalIndex,
        direct_sources: list[LectureSource],
        scores: list[float],
        context_window: int,
    ) -> list[LectureSource]:
        """Expand sources with neighboring chunks.

        Args:
            index: BM25 index with chunk metadata
            direct_sources: Direct BM25 hit sources
            scores: BM25 scores for all chunks
            context_window: Number of neighbors on each side

        Returns:
            Expanded list of sources with context, deduplicated
        """
        # Map chunk_id to index for quick lookup
        chunk_id_to_index = {
            chunk_id: idx for idx, chunk_id in enumerate(index.cache.chunk_ids)
        }

        # Collect indices including context
        expanded_indices = set()

        for source in direct_sources:
            if source.chunk_id not in chunk_id_to_index:
                continue
            center_idx = chunk_id_to_index[source.chunk_id]

            # Add neighbors
            for offset in range(-context_window, context_window + 1):
                neighbor_idx = center_idx + offset
                if 0 <= neighbor_idx < len(index.cache.chunks):
                    expanded_indices.add(neighbor_idx)

        # Build sources with is_direct_hit flag
        direct_hit_ids = {s.chunk_id for s in direct_sources}
        sources = []

        for idx in sorted(expanded_indices):
            chunk = index.cache.chunks[idx]
            is_direct = chunk["id"] in direct_hit_ids
            source = LectureSource(
                chunk_id=chunk["id"],
                type=chunk["type"],
                text=chunk["text"],
                timestamp=chunk.get("timestamp"),
                start_ms=chunk.get("start_ms"),
                end_ms=chunk.get("end_ms"),
                speaker=chunk.get("speaker"),
                bm25_score=scores[idx],
                is_direct_hit=is_direct,
            )
            sources.append(source)

        return sources


class AzureSearchLectureRetrievalService:
    """Lecture retrieval service backed by Azure AI Search."""

    def __init__(
        self,
        search_service: AzureSearchService,
    ) -> None:
        self._search_service = search_service

    async def retrieve(
        self,
        session_id: str,
        query: str,
        mode: RetrievalMode,
        top_k: int,
        context_window: int,
    ) -> list[LectureSource]:
        """Retrieve lecture sources from Azure Search."""
        normalized_top_k = max(1, top_k)
        direct_documents = await self._search_service.search_lecture_documents(
            search_text=query,
            session_id=session_id,
            top_k=normalized_top_k,
        )
        direct_sources = self._to_sources(direct_documents)[:normalized_top_k]

        if mode != "source-plus-context" or context_window <= 0:
            return direct_sources

        timeline_documents = await self._search_service.list_session_documents(
            session_id=session_id,
            max_documents=1000,
        )
        timeline_sources = self._to_sources(timeline_documents)
        if not timeline_sources:
            return direct_sources

        return self._expand_context(
            direct_sources=direct_sources,
            timeline_sources=timeline_sources,
            context_window=context_window,
        )

    async def get_index(self, session_id: str) -> LectureRetrievalIndex | None:
        """Azure retrieval does not expose a local BM25 index."""
        _ = session_id
        return None

    async def set_index(self, session_id: str, index: LectureRetrievalIndex) -> None:
        """No-op for Azure retrieval implementation."""
        _ = (session_id, index)

    async def has_index(self, session_id: str) -> bool:
        """Azure retrieval does not track in-process index existence."""
        _ = session_id
        return False

    async def remove_index(self, session_id: str) -> None:
        """No-op for Azure retrieval implementation."""
        _ = session_id

    @classmethod
    def _to_sources(cls, documents: list[dict[str, Any]]) -> list[LectureSource]:
        sources: list[LectureSource] = []
        for document in documents:
            chunk_id = str(document.get("chunk_id", "")).strip()
            if not chunk_id:
                continue

            chunk_type = str(document.get("chunk_type", "")).strip().lower()
            source_type = "visual" if chunk_type == "visual" else "speech"

            text = cls._extract_text(document)
            if not text:
                continue

            start_ms = cls._to_optional_int(document.get("start_ms"))
            end_ms = cls._to_optional_int(document.get("end_ms"))
            bm25_score = cls._to_optional_float(document.get("@search.score")) or 0.0

            sources.append(
                LectureSource(
                    chunk_id=chunk_id,
                    type=source_type,
                    text=text,
                    timestamp=cls._format_timestamp(start_ms)
                    if start_ms is not None
                    else None,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    speaker=cls._to_optional_str(document.get("speaker")),
                    bm25_score=bm25_score,
                    is_direct_hit=True,
                )
            )
        return sources

    @staticmethod
    def _extract_text(document: dict[str, Any]) -> str:
        for field in ("speech_text", "visual_text", "summary_text"):
            value = document.get(field)
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if normalized:
                return normalized
        return ""

    @staticmethod
    def _to_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_optional_str(value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _format_timestamp(start_ms: int) -> str:
        total_seconds = start_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _expand_context(
        *,
        direct_sources: list[LectureSource],
        timeline_sources: list[LectureSource],
        context_window: int,
    ) -> list[LectureSource]:
        """Expand direct hits with timeline neighbors."""
        if not direct_sources:
            return []

        index_by_chunk_id = {
            source.chunk_id: idx for idx, source in enumerate(timeline_sources)
        }
        direct_ids = {source.chunk_id for source in direct_sources}
        expanded_indices: set[int] = set()

        for direct in direct_sources:
            center_idx = index_by_chunk_id.get(direct.chunk_id)
            if center_idx is None:
                continue
            for offset in range(-context_window, context_window + 1):
                candidate = center_idx + offset
                if 0 <= candidate < len(timeline_sources):
                    expanded_indices.add(candidate)

        expanded_sources: list[LectureSource] = []
        for idx in sorted(expanded_indices):
            source = timeline_sources[idx]
            expanded_sources.append(
                source.model_copy(
                    update={"is_direct_hit": source.chunk_id in direct_ids}
                )
            )
        return expanded_sources


class ResilientLectureRetrievalService:
    """Try Azure retrieval first and fallback to BM25 when Azure returns no hits."""

    def __init__(
        self,
        *,
        primary: LectureRetrievalService,
        fallback: BM25LectureRetrievalService,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    async def retrieve(
        self,
        session_id: str,
        query: str,
        mode: RetrievalMode,
        top_k: int,
        context_window: int,
    ) -> list[LectureSource]:
        primary_sources = await self._primary.retrieve(
            session_id=session_id,
            query=query,
            mode=mode,
            top_k=top_k,
            context_window=context_window,
        )
        if primary_sources:
            return primary_sources

        logger.info(
            "lecture_retrieval_fallback_to_bm25 session_id=%s query=%r",
            session_id,
            query[:80],
        )
        return await self._fallback.retrieve(
            session_id=session_id,
            query=query,
            mode=mode,
            top_k=top_k,
            context_window=context_window,
        )

    async def get_index(self, session_id: str) -> LectureRetrievalIndex | None:
        return await self._fallback.get_index(session_id)

    async def set_index(self, session_id: str, index: LectureRetrievalIndex) -> None:
        await self._fallback.set_index(session_id, index)

    async def has_index(self, session_id: str) -> bool:
        return await self._fallback.has_index(session_id)

    async def remove_index(self, session_id: str) -> None:
        await self._fallback.remove_index(session_id)


_shared_lecture_retrieval_service: BM25LectureRetrievalService | None = None


def get_shared_lecture_retrieval_service() -> BM25LectureRetrievalService:
    """Return a process-wide shared lecture retrieval service instance."""
    global _shared_lecture_retrieval_service
    if _shared_lecture_retrieval_service is None:
        _shared_lecture_retrieval_service = BM25LectureRetrievalService()
    return _shared_lecture_retrieval_service

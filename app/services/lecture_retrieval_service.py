"""Lecture retrieval service using BM25 for local search."""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from rank_bm25 import BM25Okapi

from app.schemas.lecture_qa import LectureSource, RetrievalMode

__all__ = [
    "LectureRetrievalService",
    "BM25LectureRetrievalService",
    "BM25TokenCache",
    "LectureRetrievalIndex",
    "get_shared_lecture_retrieval_service",
]


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


_shared_lecture_retrieval_service: BM25LectureRetrievalService | None = None


def get_shared_lecture_retrieval_service() -> BM25LectureRetrievalService:
    """Return a process-wide shared lecture retrieval service instance."""
    global _shared_lecture_retrieval_service
    if _shared_lecture_retrieval_service is None:
        _shared_lecture_retrieval_service = BM25LectureRetrievalService()
    return _shared_lecture_retrieval_service

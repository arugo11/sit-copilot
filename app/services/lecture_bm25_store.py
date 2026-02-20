"""In-memory BM25 index cache with thread-safe operations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

__all__ = ["LectureBM25Index", "LectureBM25Store"]


@dataclass
class LectureBM25Index:
    """BM25 index data for a single lecture session."""

    session_id: str
    chunks: list[dict[str, Any]]  # BM25 corpus with metadata
    tokenized_corpus: list[list[str]]  # Pre-tokenized for thread-safe retrieval
    chunk_map: dict[str, dict[str, Any]]  # chunk_id -> chunk data lookup
    index_version: str  # UUID or timestamp
    created_at: datetime


class LectureBM25Store:
    """Thread-safe in-memory cache for BM25 indices keyed by session_id.

    ⚠️ rank-bm25 is NOT thread-safe. We store tokenized corpus and create
    BM25Okapi instance per retrieval request to ensure thread safety.
    """

    def __init__(self) -> None:
        self._indices: dict[str, LectureBM25Index] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._store_lock = asyncio.Lock()

    async def get(self, session_id: str) -> LectureBM25Index | None:
        """Get BM25 index for session. Returns None if not found."""
        async with self._store_lock:
            return self._indices.get(session_id)

    async def put(
        self,
        session_id: str,
        chunks: list[dict[str, Any]],
        tokenized_corpus: list[list[str]],
        index_version: str,
    ) -> None:
        """Store BM25 index for session. Replaces existing if present."""
        # Build chunk_map for fast lookup by chunk_id
        chunk_map = {chunk["id"]: chunk for chunk in chunks}

        index = LectureBM25Index(
            session_id=session_id,
            chunks=chunks,
            tokenized_corpus=tokenized_corpus,
            chunk_map=chunk_map,
            index_version=index_version,
            created_at=datetime.now(UTC),
        )

        async with self._store_lock:
            self._indices[session_id] = index
            # Ensure lock exists for this session
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()

    async def delete(self, session_id: str) -> None:
        """Remove BM25 index for session."""
        async with self._store_lock:
            self._indices.pop(session_id, None)
            self._locks.pop(session_id, None)

    async def acquire_lock(self, session_id: str) -> asyncio.Lock:
        """Get or create lock for session-specific index operations."""
        async with self._store_lock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
            return self._locks[session_id]

    async def has_index(self, session_id: str) -> bool:
        """Check if index exists for session."""
        async with self._store_lock:
            return session_id in self._indices

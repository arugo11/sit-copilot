"""Lecture index service for building BM25 search indexes."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.schemas.lecture_qa import LectureIndexBuildResponse
from app.services.lecture_live_service import LectureSessionNotFoundError
from app.services.lecture_retrieval_service import (
    BM25LectureRetrievalService,
    BM25TokenCache,
    LectureRetrievalIndex,
)

__all__ = ["LectureIndexService", "BM25LectureIndexService"]


class LectureIndexService(Protocol):
    """Interface for building and managing lecture search indexes."""

    async def build_index(
        self,
        session_id: str,
        user_id: str,
        rebuild: bool,
    ) -> LectureIndexBuildResponse:
        """Build or rebuild BM25 index for a lecture session."""
        ...


class BM25LectureIndexService:
    """BM25 index builder with per-session concurrency control."""

    DEFAULT_K1 = 1.2
    DEFAULT_B = 0.5

    def __init__(
        self,
        db: AsyncSession,
        retrieval_service: BM25LectureRetrievalService,
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
    ) -> None:
        """Initialize the index service.

        Args:
            db: Database session for fetching speech events
            retrieval_service: Retrieval service to store the built index
            k1: BM25 term frequency parameter
            b: BM25 length normalization parameter
        """
        self._db = db
        self._retrieval_service = retrieval_service
        self._k1 = k1
        self._b = b
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        """Get or create a per-session lock for concurrency control."""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def build_index(
        self,
        session_id: str,
        user_id: str,
        rebuild: bool,
    ) -> LectureIndexBuildResponse:
        """Build or rebuild BM25 index for a lecture session.

        Args:
            session_id: Lecture session identifier
            user_id: User ID for ownership validation
            rebuild: Force rebuild even if index exists

        Returns:
            Response with index version, chunk count, and build status

        Raises:
            LectureSessionNotFoundError: If session not found or ownership validation fails
        """
        # Use per-session lock to prevent concurrent builds
        async with self._get_lock(session_id):
            return await self._build_index_locked(session_id, user_id, rebuild)

    async def _build_index_locked(
        self,
        session_id: str,
        user_id: str,
        rebuild: bool,
    ) -> LectureIndexBuildResponse:
        """Build index with lock held."""
        # Validate session ownership
        await self._get_session_with_ownership(session_id, user_id)

        # Check if index already exists
        has_index = await self._retrieval_service.has_index(session_id)
        if has_index and not rebuild:
            return LectureIndexBuildResponse(
                index_version=session_id,
                chunk_count=0,
                built_at=datetime.now(UTC),
                status="skipped",
            )

        # Fetch finalized speech events
        events = await self._fetch_speech_events(session_id)

        if not events:
            # No events to index, but mark as built
            await self._mark_index_built(session_id)
            return LectureIndexBuildResponse(
                index_version=self._generate_version(),
                chunk_count=0,
                built_at=datetime.now(UTC),
                status="success",
            )

        # Build BM25 index
        index = await self._build_bm25_index(events)

        # Store index in retrieval service
        await self._retrieval_service.set_index(session_id, index)

        # Mark session as indexed
        await self._mark_index_built(session_id)

        return LectureIndexBuildResponse(
            index_version=self._generate_version(),
            chunk_count=len(events),
            built_at=datetime.now(UTC),
            status="success",
        )

    async def _get_session_with_ownership(
        self, session_id: str, user_id: str
    ) -> LectureSession:
        """Get session with ownership validation.

        Args:
            session_id: Session identifier
            user_id: User ID to validate ownership

        Returns:
            The lecture session

        Raises:
            LectureSessionNotFoundError: If session not found or ownership mismatch
        """
        result = await self._db.execute(
            select(LectureSession).where(
                LectureSession.id == session_id,
                LectureSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()

        if session is None:
            raise LectureSessionNotFoundError(
                f"lecture session not found: {session_id}"
            )

        return session

    async def _fetch_speech_events(self, session_id: str) -> list[SpeechEvent]:
        """Fetch finalized speech events for indexing.

        Args:
            session_id: Session identifier

        Returns:
            List of finalized speech events ordered by start time
        """
        result = await self._db.execute(
            select(SpeechEvent)
            .where(
                SpeechEvent.session_id == session_id,
                SpeechEvent.is_final == True,  # noqa: E712
            )
            .order_by(SpeechEvent.start_ms)
        )
        return list(result.scalars().all())

    async def _build_bm25_index(
        self, events: list[SpeechEvent]
    ) -> LectureRetrievalIndex:
        """Build BM25 index from speech events.

        Args:
            events: List of speech events to index

        Returns:
            BM25 index with token cache
        """
        # Prepare chunks and tokenized corpus
        chunks = []
        tokenized_corpus = []
        chunk_ids = []

        for event in events:
            chunk_id = event.id
            chunk_ids.append(chunk_id)

            # Store chunk metadata
            chunk = {
                "id": chunk_id,
                "type": "speech",
                "text": event.text,
                "timestamp": self._format_timestamp(event.start_ms),
                "start_ms": event.start_ms,
                "end_ms": event.end_ms,
                "speaker": event.speaker,
            }
            chunks.append(chunk)

            # Tokenize text (simple whitespace + lowercase)
            tokens = self._tokenize(event.text)
            tokenized_corpus.append(tokens)

        # Create token cache
        cache = BM25TokenCache(
            tokenized_corpus=tokenized_corpus,
            chunk_ids=chunk_ids,
            chunks=chunks,
        )

        # Build BM25 index in thread pool (CPU-bound)
        from rank_bm25 import BM25Okapi

        bm25 = await asyncio.to_thread(
            BM25Okapi, tokenized_corpus, k1=self._k1, b=self._b
        )

        return LectureRetrievalIndex(
            bm25=bm25,
            cache=cache,
            k1=self._k1,
            b=self._b,
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text for BM25 indexing.

        Uses simple whitespace tokenization with lowercasing.
        For production, consider integrating SudachiPy for Japanese.
        """
        return text.lower().split()

    @staticmethod
    def _format_timestamp(start_ms: int) -> str:
        """Format milliseconds to MM:SS timestamp.

        Args:
            start_ms: Start time in milliseconds

        Returns:
            Formatted timestamp string (e.g., "05:23")
        """
        total_seconds = start_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _generate_version() -> str:
        """Generate a unique index version identifier."""
        return str(uuid.uuid4())

    async def _mark_index_built(self, session_id: str) -> None:
        """Mark session as having a built index.

        Args:
            session_id: Session identifier
        """
        result = await self._db.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        session = result.scalar_one_or_none()

        if session is not None:
            session.qa_index_built = True
            await self._db.flush()

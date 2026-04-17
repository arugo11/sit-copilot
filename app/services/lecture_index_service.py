"""Lecture index service for BM25 and Azure Search index builds."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from rank_bm25 import BM25Okapi
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_chunk import LectureChunk
from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.schemas.lecture_qa import LectureIndexBuildResponse
from app.services.azure_search_service import AzureSearchService
from app.services.lecture_live_service import LectureSessionNotFoundError
from app.services.lecture_retrieval_service import (
    BM25LectureRetrievalService,
    BM25TokenCache,
    LectureRetrievalIndex,
    TokenizerMode,
    tokenize_hybrid_japanese_text,
    tokenize_whitespace_text,
)

__all__ = [
    "LectureIndexService",
    "BM25LectureIndexService",
    "AzureLectureIndexService",
]


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
        tokenizer_mode: TokenizerMode = "whitespace",
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
        self._tokenizer_mode = tokenizer_mode
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

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text for BM25 indexing."""
        if self._tokenizer_mode == "hybrid":
            return tokenize_hybrid_japanese_text(text)
        return tokenize_whitespace_text(text)

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


class AzureLectureIndexService:
    """Azure Search index builder with per-session concurrency control."""

    def __init__(
        self,
        db: AsyncSession,
        search_service: AzureSearchService,
        local_retrieval_service: BM25LectureRetrievalService | None = None,
        tokenizer_mode: TokenizerMode = "hybrid",
    ) -> None:
        self._db = db
        self._search_service = search_service
        self._local_retrieval_service = local_retrieval_service
        self._tokenizer_mode = tokenizer_mode
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
        """Build or rebuild Azure Search documents for a lecture session."""
        async with self._get_lock(session_id):
            return await self._build_index_locked(session_id, user_id, rebuild)

    async def _build_index_locked(
        self,
        session_id: str,
        user_id: str,
        rebuild: bool,
    ) -> LectureIndexBuildResponse:
        session = await self._get_session_with_ownership(session_id, user_id)
        has_remote_documents = await self._search_service.has_session_documents(
            session_id=session_id
        )
        if session.qa_index_built and has_remote_documents and not rebuild:
            return LectureIndexBuildResponse(
                index_version=session_id,
                chunk_count=0,
                built_at=datetime.now(UTC),
                status="skipped",
            )

        documents, persistable_chunk_ids = await self._build_documents(session)
        if not documents:
            session.qa_index_built = True
            await self._db.flush()
            return LectureIndexBuildResponse(
                index_version=self._generate_version(),
                chunk_count=0,
                built_at=datetime.now(UTC),
                status="success",
            )

        succeeded_chunk_ids = await self._search_service.upsert_lecture_documents(
            documents
        )
        if len(succeeded_chunk_ids) != len(documents):
            raise RuntimeError(
                "azure search indexing failed for one or more lecture documents"
            )

        await self._sync_indexed_flags(
            session_id=session.id,
            persistable_chunk_ids=persistable_chunk_ids,
            succeeded_chunk_ids=succeeded_chunk_ids,
        )
        await self._sync_local_index(
            session=session,
            documents=documents,
            succeeded_chunk_ids=succeeded_chunk_ids,
        )

        session.qa_index_built = True
        await self._db.flush()

        return LectureIndexBuildResponse(
            index_version=self._generate_version(),
            chunk_count=len(succeeded_chunk_ids),
            built_at=datetime.now(UTC),
            status="success",
        )

    async def _build_documents(
        self,
        session: LectureSession,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        chunks = await self._fetch_lecture_chunks(session.id)
        if chunks:
            documents = [
                self._to_document_from_chunk(session, chunk) for chunk in chunks
            ]
            chunk_ids = [chunk.id for chunk in chunks]
            return documents, chunk_ids

        events = await self._fetch_speech_events(session.id)
        documents = [self._to_document_from_event(session, event) for event in events]
        return documents, []

    async def _sync_indexed_flags(
        self,
        *,
        session_id: str,
        persistable_chunk_ids: list[str],
        succeeded_chunk_ids: list[str],
    ) -> None:
        if not persistable_chunk_ids:
            return

        await self._db.execute(
            update(LectureChunk)
            .where(LectureChunk.session_id == session_id)
            .values(indexed_to_search=False)
        )
        await self._db.execute(
            update(LectureChunk)
            .where(
                LectureChunk.session_id == session_id,
                LectureChunk.id.in_(succeeded_chunk_ids),
            )
            .values(indexed_to_search=True)
        )
        await self._db.flush()

    async def _get_session_with_ownership(
        self,
        session_id: str,
        user_id: str,
    ) -> LectureSession:
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

    async def _fetch_lecture_chunks(self, session_id: str) -> list[LectureChunk]:
        result = await self._db.execute(
            select(LectureChunk)
            .where(LectureChunk.session_id == session_id)
            .order_by(LectureChunk.start_ms)
        )
        return list(result.scalars().all())

    async def _fetch_speech_events(self, session_id: str) -> list[SpeechEvent]:
        result = await self._db.execute(
            select(SpeechEvent)
            .where(
                SpeechEvent.session_id == session_id,
                SpeechEvent.is_final == True,  # noqa: E712
            )
            .order_by(SpeechEvent.start_ms)
        )
        return list(result.scalars().all())

    @staticmethod
    def _to_document_from_chunk(
        session: LectureSession,
        chunk: LectureChunk,
    ) -> dict[str, Any]:
        started_at = session.started_at.date().isoformat() if session.started_at else ""
        keywords = [
            str(keyword).strip()
            for keyword in (chunk.keywords_json or [])
            if str(keyword).strip()
        ]
        return {
            "chunk_id": chunk.id,
            "session_id": chunk.session_id,
            "course_name": session.course_name,
            "date": started_at,
            "chunk_type": chunk.chunk_type,
            "start_ms": chunk.start_ms,
            "end_ms": chunk.end_ms,
            "speech_text": chunk.speech_text or "",
            "visual_text": chunk.visual_text or "",
            "summary_text": chunk.summary_text or "",
            "keywords": " ".join(keywords),
            "lang": session.lang_mode,
            "speaker": "",
        }

    @staticmethod
    def _to_document_from_event(
        session: LectureSession,
        event: SpeechEvent,
    ) -> dict[str, Any]:
        started_at = session.started_at.date().isoformat() if session.started_at else ""
        return {
            "chunk_id": event.id,
            "session_id": event.session_id,
            "course_name": session.course_name,
            "date": started_at,
            "chunk_type": "speech",
            "start_ms": event.start_ms,
            "end_ms": event.end_ms,
            "speech_text": event.text,
            "visual_text": "",
            "summary_text": "",
            "keywords": "",
            "lang": session.lang_mode,
            "speaker": event.speaker,
        }

    @staticmethod
    def _generate_version() -> str:
        """Generate a unique index version identifier."""
        return str(uuid.uuid4())

    async def _sync_local_index(
        self,
        *,
        session: LectureSession,
        documents: list[dict[str, Any]],
        succeeded_chunk_ids: list[str],
    ) -> None:
        if self._local_retrieval_service is None:
            return

        succeeded_ids = set(succeeded_chunk_ids)
        chunks = [
            self._document_to_bm25_chunk(document)
            for document in documents
            if str(document.get("chunk_id", "")) in succeeded_ids
        ]
        tokenized_corpus = [self._tokenize(chunk["text"]) for chunk in chunks]
        chunk_ids = [chunk["id"] for chunk in chunks]

        index = LectureRetrievalIndex(
            bm25=BM25Okapi(tokenized_corpus),
            cache=BM25TokenCache(
                tokenized_corpus=tokenized_corpus,
                chunk_ids=chunk_ids,
                chunks=chunks,
            ),
            k1=BM25LectureIndexService.DEFAULT_K1,
            b=BM25LectureIndexService.DEFAULT_B,
        )
        await self._local_retrieval_service.set_index(session.id, index)

    def _document_to_bm25_chunk(self, document: dict[str, Any]) -> dict[str, Any]:
        text = ""
        for field in ("speech_text", "visual_text", "summary_text"):
            value = document.get(field)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break

        return {
            "id": str(document.get("chunk_id", "")).strip(),
            "type": "visual"
            if str(document.get("chunk_type", "")).strip().lower() == "visual"
            else "speech",
            "text": text,
            "timestamp": self._format_timestamp(document.get("start_ms")),
            "start_ms": self._to_optional_int(document.get("start_ms")),
            "end_ms": self._to_optional_int(document.get("end_ms")),
            "speaker": str(document.get("speaker", "")).strip() or None,
        }

    def _tokenize(self, text: str) -> list[str]:
        if self._tokenizer_mode == "hybrid":
            return tokenize_hybrid_japanese_text(text)
        return tokenize_whitespace_text(text)

    @staticmethod
    def _to_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _format_timestamp(cls, start_ms: Any) -> str | None:
        normalized = cls._to_optional_int(start_ms)
        if normalized is None:
            return None
        total_seconds = normalized // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

"""Lecture finalize service for artifact generation and session closure."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_chunk import LectureChunk
from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.summary_window import SummaryWindow
from app.models.visual_event import VisualEvent
from app.schemas.lecture import (
    LectureSessionFinalizeResponse,
    LectureSessionFinalizeStats,
)
from app.services.lecture_index_service import LectureIndexService
from app.services.lecture_live_service import LectureSessionNotFoundError
from app.services.lecture_summary_service import LectureSummaryService

__all__ = [
    "LectureFinalizeService",
    "LectureSessionStateError",
    "SqlAlchemyLectureFinalizeService",
]

MAX_EMBEDDING_TEXT_CHARS = 1000
logger = logging.getLogger(__name__)


class LectureSessionStateError(Exception):
    """Raised when session state does not allow finalize flow."""


@dataclass
class _FinalizeStats:
    speech_events: int
    visual_events: int
    summary_windows: int
    lecture_chunks: int


class LectureFinalizeService(Protocol):
    """Interface for lecture session finalization."""

    async def finalize(
        self,
        session_id: str,
        build_qa_index: bool,
    ) -> LectureSessionFinalizeResponse:
        """Finalize a lecture session and generate artifacts."""
        ...


class SqlAlchemyLectureFinalizeService:
    """SQLAlchemy implementation of lecture session finalization."""

    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        summary_service: LectureSummaryService,
        index_service: LectureIndexService | None = None,
    ) -> None:
        self._db = db
        self._user_id = user_id
        self._summary_service = summary_service
        self._index_service = index_service

    async def finalize(
        self,
        session_id: str,
        build_qa_index: bool,
    ) -> LectureSessionFinalizeResponse:
        """Finalize a lecture session with idempotent behavior."""
        session = await self._get_session_with_ownership(session_id)

        if session.status not in {"active", "finalized"}:
            raise LectureSessionStateError(
                f"session status does not allow finalize: {session.status}"
            )

        if session.status == "active":
            await self._summary_service.rebuild_windows(
                session_id=session_id,
                user_id=self._user_id,
            )
            await self._rebuild_chunks(session_id)
            session.status = "finalized"
            if session.ended_at is None:
                session.ended_at = datetime.now(UTC)

        if build_qa_index:
            build_success = await self._build_qa_index(session_id)
            session.qa_index_built = session.qa_index_built or build_success

        stats = await self._collect_stats(session_id)
        response_stats = LectureSessionFinalizeStats(
            speech_events=stats.speech_events,
            visual_events=stats.visual_events,
            summary_windows=stats.summary_windows,
            lecture_chunks=stats.lecture_chunks,
        )

        return LectureSessionFinalizeResponse(
            session_id=session_id,
            status="finalized",
            note_generated=stats.summary_windows > 0,
            qa_index_built=session.qa_index_built,
            stats=response_stats,
        )

    async def _get_session_with_ownership(self, session_id: str) -> LectureSession:
        result = await self._db.execute(
            select(LectureSession).where(
                LectureSession.id == session_id,
                LectureSession.user_id == self._user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise LectureSessionNotFoundError(
                f"lecture session not found: {session_id}"
            )
        return session

    async def _build_qa_index(self, session_id: str) -> bool:
        if self._index_service is None:
            return False
        try:
            result = await self._index_service.build_index(
                session_id=session_id,
                user_id=self._user_id,
                rebuild=True,
            )
            return result.status in {"success", "skipped"}
        except Exception:
            logger.warning(
                "Lecture QA index build failed during finalize: session_id=%s",
                session_id,
                exc_info=True,
            )
            return False

    async def _rebuild_chunks(self, session_id: str) -> None:
        await self._db.execute(
            delete(LectureChunk).where(LectureChunk.session_id == session_id)
        )

        speech_events = await self._fetch_speech_events(session_id)
        visual_events = await self._fetch_visual_events(session_id)
        summary_windows = await self._fetch_summary_windows(session_id)

        for event in speech_events:
            text = event.text.strip()
            chunk = LectureChunk(
                session_id=session_id,
                chunk_type="speech",
                start_ms=event.start_ms,
                end_ms=event.end_ms,
                speech_text=text,
                visual_text=None,
                summary_text=None,
                keywords_json=_extract_keywords(text),
                embedding_text=text[:MAX_EMBEDDING_TEXT_CHARS],
                indexed_to_search=False,
            )
            self._db.add(chunk)

        for event in visual_events:
            text = event.ocr_text.strip()
            chunk = LectureChunk(
                session_id=session_id,
                chunk_type="visual",
                start_ms=event.timestamp_ms,
                end_ms=event.timestamp_ms,
                speech_text=None,
                visual_text=text,
                summary_text=None,
                keywords_json=_extract_keywords(text),
                embedding_text=text[:MAX_EMBEDDING_TEXT_CHARS],
                indexed_to_search=False,
            )
            self._db.add(chunk)

        for window in summary_windows:
            text = window.summary_text.strip()
            chunk = LectureChunk(
                session_id=session_id,
                chunk_type="merged",
                start_ms=window.start_ms,
                end_ms=window.end_ms,
                speech_text=None,
                visual_text=None,
                summary_text=text,
                keywords_json=_extract_keywords(text),
                embedding_text=text[:MAX_EMBEDDING_TEXT_CHARS],
                indexed_to_search=False,
            )
            self._db.add(chunk)

        await self._db.flush()

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

    async def _fetch_visual_events(self, session_id: str) -> list[VisualEvent]:
        result = await self._db.execute(
            select(VisualEvent)
            .where(
                VisualEvent.session_id == session_id,
                VisualEvent.quality != "bad",
            )
            .order_by(VisualEvent.timestamp_ms)
        )
        return list(result.scalars().all())

    async def _fetch_summary_windows(self, session_id: str) -> list[SummaryWindow]:
        result = await self._db.execute(
            select(SummaryWindow)
            .where(SummaryWindow.session_id == session_id)
            .order_by(SummaryWindow.start_ms)
        )
        return list(result.scalars().all())

    async def _collect_stats(self, session_id: str) -> _FinalizeStats:
        speech_result = await self._db.execute(
            select(func.count(SpeechEvent.id)).where(
                SpeechEvent.session_id == session_id
            )
        )
        visual_result = await self._db.execute(
            select(func.count(VisualEvent.id)).where(
                VisualEvent.session_id == session_id
            )
        )
        summary_result = await self._db.execute(
            select(func.count(SummaryWindow.id)).where(
                SummaryWindow.session_id == session_id
            )
        )
        chunk_result = await self._db.execute(
            select(func.count(LectureChunk.id)).where(
                LectureChunk.session_id == session_id
            )
        )

        return _FinalizeStats(
            speech_events=int(speech_result.scalar_one()),
            visual_events=int(visual_result.scalar_one()),
            summary_windows=int(summary_result.scalar_one()),
            lecture_chunks=int(chunk_result.scalar_one()),
        )


def _extract_keywords(text: str) -> list[str]:
    """Extract lightweight keyword candidates for chunk metadata."""
    candidates = re.split(r"[、,。\s/・:;()（）「」『』\[\]{}]+", text)
    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        token = candidate.strip()
        if len(token) < 2 or len(token) > 24:
            continue
        if token in seen:
            continue
        seen.add(token)
        keywords.append(token)
        if len(keywords) >= 8:
            break
    return keywords

"""Lecture summary service for 30-second window generation."""

from __future__ import annotations

import re
from typing import Literal, Protocol

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.summary_window import SummaryWindow
from app.models.visual_event import VisualEvent
from app.schemas.lecture import (
    LectureEvidenceType,
    LectureSummaryEvidence,
    LectureSummaryKeyTerm,
    LectureSummaryLatestResponse,
)
from app.services.lecture_live_service import (
    LectureSessionInactiveError,
    LectureSessionNotFoundError,
)

__all__ = ["LectureSummaryService", "SqlAlchemyLectureSummaryService"]

WINDOW_SIZE_MS = 30_000
LOOKBACK_MS = 60_000
MAX_SUMMARY_CHARS = 600
MAX_KEY_TERMS = 5
MAX_EVIDENCE_ITEMS = 6
EVIDENCE_TAG_ORDER: tuple[LectureEvidenceType, ...] = ("speech", "slide", "board")


class LectureSummaryService(Protocol):
    """Interface for lecture summary window generation."""

    async def get_latest_summary(
        self,
        session_id: str,
        user_id: str,
    ) -> LectureSummaryLatestResponse:
        """Build and return the latest summary window."""
        ...

    async def rebuild_windows(
        self,
        session_id: str,
        user_id: str,
    ) -> int:
        """Rebuild all summary windows for a session."""
        ...


class SqlAlchemyLectureSummaryService:
    """SQLAlchemy-based implementation for deterministic summary generation."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_latest_summary(
        self,
        session_id: str,
        user_id: str,
    ) -> LectureSummaryLatestResponse:
        """Build and return the latest summary window for a session."""
        await self._get_session_with_ownership(session_id, user_id)

        max_event_ms = await self._get_max_event_ms(session_id)
        if max_event_ms is None:
            return LectureSummaryLatestResponse(
                session_id=session_id,
                window_start_ms=0,
                window_end_ms=0,
                summary="要約に利用できる講義データがありません。",
                key_terms=[],
                evidence=[],
                status="no_data",
            )

        window_end_ms = _to_window_end(max_event_ms)
        return await self._build_window(
            session_id=session_id,
            window_end_ms=window_end_ms,
            persist=True,
        )

    async def rebuild_windows(
        self,
        session_id: str,
        user_id: str,
    ) -> int:
        """Rebuild all windows from session start to latest event timestamp."""
        await self._get_session_with_ownership(session_id, user_id)

        max_event_ms = await self._get_max_event_ms(session_id)
        if max_event_ms is None:
            return 0

        last_window_end_ms = _to_window_end(max_event_ms)
        for window_end_ms in range(
            WINDOW_SIZE_MS, last_window_end_ms + 1, WINDOW_SIZE_MS
        ):
            await self._build_window(
                session_id=session_id,
                window_end_ms=window_end_ms,
                persist=True,
            )

        return await self._count_summary_windows(session_id)

    async def _build_window(
        self,
        *,
        session_id: str,
        window_end_ms: int,
        persist: bool,
    ) -> LectureSummaryLatestResponse:
        window_start_ms = max(0, window_end_ms - WINDOW_SIZE_MS)
        lookback_start_ms = max(0, window_end_ms - LOOKBACK_MS)

        speech_events = await self._fetch_speech_events(
            session_id=session_id,
            start_ms=lookback_start_ms,
            end_ms=window_end_ms,
        )
        visual_events = await self._fetch_visual_events(
            session_id=session_id,
            start_ms=lookback_start_ms,
            end_ms=window_end_ms,
        )

        summary_text = self._build_summary_text(
            speech_events=speech_events,
            visual_events=visual_events,
        )
        evidence = self._build_evidence(
            speech_events=speech_events,
            visual_events=visual_events,
        )
        key_terms = self._build_key_terms(
            speech_events=speech_events,
            visual_events=visual_events,
            evidence=evidence,
        )
        status = "ok" if evidence else "no_data"

        if persist:
            await self._upsert_summary_window(
                session_id=session_id,
                window_start_ms=window_start_ms,
                window_end_ms=window_end_ms,
                summary_text=summary_text,
                key_terms=key_terms,
                evidence=evidence,
            )

        return LectureSummaryLatestResponse(
            session_id=session_id,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            summary=summary_text,
            key_terms=key_terms,
            evidence=evidence,
            status=status,
        )

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
        if session.status not in {"active", "finalized"}:
            raise LectureSessionInactiveError(
                f"lecture session state does not allow summary: {session.status}"
            )
        return session

    async def _get_max_event_ms(self, session_id: str) -> int | None:
        speech_result = await self._db.execute(
            select(func.max(SpeechEvent.end_ms)).where(
                SpeechEvent.session_id == session_id,
                SpeechEvent.is_final == True,  # noqa: E712
            )
        )
        visual_result = await self._db.execute(
            select(func.max(VisualEvent.timestamp_ms)).where(
                VisualEvent.session_id == session_id
            )
        )
        speech_max = speech_result.scalar_one_or_none()
        visual_max = visual_result.scalar_one_or_none()

        values = [value for value in [speech_max, visual_max] if value is not None]
        if not values:
            return None
        return max(values)

    async def _fetch_speech_events(
        self,
        *,
        session_id: str,
        start_ms: int,
        end_ms: int,
    ) -> list[SpeechEvent]:
        result = await self._db.execute(
            select(SpeechEvent)
            .where(
                SpeechEvent.session_id == session_id,
                SpeechEvent.is_final == True,  # noqa: E712
                SpeechEvent.end_ms >= start_ms,
                SpeechEvent.start_ms <= end_ms,
            )
            .order_by(SpeechEvent.start_ms)
        )
        return list(result.scalars().all())

    async def _fetch_visual_events(
        self,
        *,
        session_id: str,
        start_ms: int,
        end_ms: int,
    ) -> list[VisualEvent]:
        result = await self._db.execute(
            select(VisualEvent)
            .where(
                VisualEvent.session_id == session_id,
                VisualEvent.timestamp_ms >= start_ms,
                VisualEvent.timestamp_ms <= end_ms,
                VisualEvent.quality != "bad",
            )
            .order_by(VisualEvent.timestamp_ms)
        )
        return list(result.scalars().all())

    async def _upsert_summary_window(
        self,
        *,
        session_id: str,
        window_start_ms: int,
        window_end_ms: int,
        summary_text: str,
        key_terms: list[LectureSummaryKeyTerm],
        evidence: list[LectureSummaryEvidence],
    ) -> None:
        key_terms_json = [term.model_dump() for term in key_terms]
        evidence_refs = [f"{item.type}:{item.ref_id}" for item in evidence]
        upsert_stmt = sqlite_insert(SummaryWindow).values(
            session_id=session_id,
            start_ms=window_start_ms,
            end_ms=window_end_ms,
            summary_text=summary_text,
            key_terms_json=key_terms_json,
            evidence_event_ids_json=evidence_refs,
        )
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["session_id", "start_ms", "end_ms"],
            set_={
                "summary_text": summary_text,
                "key_terms_json": key_terms_json,
                "evidence_event_ids_json": evidence_refs,
            },
        )
        await self._db.execute(upsert_stmt)
        await self._db.flush()

    async def _count_summary_windows(self, session_id: str) -> int:
        result = await self._db.execute(
            select(func.count(SummaryWindow.id)).where(
                SummaryWindow.session_id == session_id
            )
        )
        count = result.scalar_one()
        return int(count)

    @staticmethod
    def _build_summary_text(
        *,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
    ) -> str:
        speech_text = " ".join(
            event.text.strip() for event in speech_events if event.text.strip()
        )
        visual_text = " / ".join(
            event.ocr_text.strip() for event in visual_events if event.ocr_text.strip()
        )

        if speech_text and visual_text:
            summary = f"この区間では、{speech_text}。視覚情報では {visual_text} が確認されました。"
        elif speech_text:
            summary = f"この区間では、{speech_text}"
        elif visual_text:
            summary = f"この区間では、視覚情報として {visual_text} が確認されました。"
        else:
            summary = "この区間の要約を生成できるデータがありません。"

        return summary[:MAX_SUMMARY_CHARS]

    @staticmethod
    def _build_evidence(
        *,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
    ) -> list[LectureSummaryEvidence]:
        evidence: list[LectureSummaryEvidence] = []

        for event in speech_events[-3:]:
            evidence.append(
                LectureSummaryEvidence(
                    type="speech",
                    ref_id=event.id,
                )
            )
        for event in visual_events[-3:]:
            evidence_type: Literal["slide", "board"] = (
                "slide" if event.source == "slide" else "board"
            )
            evidence.append(
                LectureSummaryEvidence(
                    type=evidence_type,
                    ref_id=event.id,
                )
            )

        return evidence[:MAX_EVIDENCE_ITEMS]

    @staticmethod
    def _build_key_terms(
        *,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
        evidence: list[LectureSummaryEvidence],
    ) -> list[LectureSummaryKeyTerm]:
        source_tags: list[LectureEvidenceType] = []
        for candidate in EVIDENCE_TAG_ORDER:
            if any(item.type == candidate for item in evidence):
                source_tags.append(candidate)

        visual_tokens = _tokenize_terms(
            " ".join(event.ocr_text for event in visual_events if event.ocr_text)
        )
        speech_tokens = _tokenize_terms(
            " ".join(event.text for event in speech_events if event.text)
        )

        candidates = visual_tokens + speech_tokens
        unique_terms = _dedupe_terms(candidates)

        if not unique_terms:
            fallback_text = next(
                (event.text.strip() for event in speech_events if event.text.strip()),
                "",
            )
            if fallback_text:
                unique_terms = [fallback_text[:12]]

        terms = []
        default_tags: list[LectureEvidenceType] = ["speech"]
        for term in unique_terms[:MAX_KEY_TERMS]:
            terms.append(
                LectureSummaryKeyTerm(
                    term=term,
                    evidence_tags=source_tags if source_tags else default_tags,
                )
            )
        return terms


def _to_window_end(event_ms: int) -> int:
    """Round event timestamp up to the corresponding 30-second window end."""
    if event_ms <= 0:
        return WINDOW_SIZE_MS
    return ((event_ms + WINDOW_SIZE_MS - 1) // WINDOW_SIZE_MS) * WINDOW_SIZE_MS


def _tokenize_terms(text: str) -> list[str]:
    """Extract candidate term tokens with lightweight normalization."""
    candidates = re.split(r"[、,。\s/・:;()（）「」『』\[\]{}]+", text)
    terms: list[str] = []
    for candidate in candidates:
        token = candidate.strip()
        if 2 <= len(token) <= 24:
            terms.append(token)
    return terms


def _dedupe_terms(terms: list[str]) -> list[str]:
    """Deduplicate terms while preserving order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        deduped.append(term)
    return deduped

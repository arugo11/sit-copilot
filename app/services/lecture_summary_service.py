"""Lecture summary service for 30-second window generation."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Literal, Protocol

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_id import get_user_id_candidates
from app.db.session import commit_with_retry, is_sqlite_locked_error
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
from app.services.lecture_summary_generator_service import (
    LectureSummaryGeneratorService,
)

__all__ = ["LectureSummaryService", "SqlAlchemyLectureSummaryService"]

logger = logging.getLogger(__name__)

WINDOW_SIZE_MS = 30_000
LOOKBACK_MS = 60_000
MAX_SUMMARY_CHARS = 600
MAX_KEY_TERMS = 5
MAX_KEY_TERM_EVIDENCE_TAGS = 3
MAX_EVIDENCE_ITEMS = 6
EVIDENCE_TAG_ORDER: tuple[LectureEvidenceType, ...] = ("speech", "slide", "board")
SUMMARY_ALLOWED_SESSION_STATUSES = {"active", "live", "finalized"}
WRITE_RETRY_ATTEMPTS = 5
WRITE_RETRY_BASE_DELAY_SECONDS = 0.05
DEFAULT_MAX_REBUILD_WINDOWS = 1_200
NO_DATA_SUMMARY_MESSAGE = "要約に利用できる講義データがありません。"


class LectureSummaryService(Protocol):
    """Interface for lecture summary window generation."""

    async def get_latest_summary(
        self,
        session_id: str,
        user_id: str,
        force_rebuild: bool = False,
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
    """SQLAlchemy-based implementation for LLM-powered summary generation."""

    def __init__(
        self,
        db: AsyncSession,
        summary_generator: LectureSummaryGeneratorService,
        *,
        max_rebuild_windows: int = DEFAULT_MAX_REBUILD_WINDOWS,
    ) -> None:
        self._db = db
        self._summary_generator = summary_generator
        self._max_rebuild_windows = max(1, max_rebuild_windows)

    async def get_latest_summary(
        self,
        session_id: str,
        user_id: str,
        force_rebuild: bool = False,
    ) -> LectureSummaryLatestResponse:
        """Build and return the latest summary window for a session."""
        session = await self._get_session_with_ownership(session_id, user_id)

        event_bounds = await self._get_event_bounds(session_id)
        if event_bounds is None:
            return LectureSummaryLatestResponse(
                session_id=session_id,
                window_start_ms=0,
                window_end_ms=0,
                summary=NO_DATA_SUMMARY_MESSAGE,
                key_terms=[],
                evidence=[],
                status="no_data",
            )

        _, max_event_ms = event_bounds
        window_end_ms = _to_window_end(max_event_ms)
        if not force_rebuild:
            existing_window = await self._get_summary_window(
                session_id=session_id,
                window_end_ms=window_end_ms,
            )
            if existing_window is not None:
                return self._response_from_summary_window(existing_window)

        return await self._build_window(
            session_id=session_id,
            window_end_ms=window_end_ms,
            persist=True,
            lang_mode=session.lang_mode,
        )

    async def rebuild_windows(
        self,
        session_id: str,
        user_id: str,
    ) -> int:
        """Rebuild all windows from session start to latest event timestamp."""
        session = await self._get_session_with_ownership(session_id, user_id)

        event_bounds = await self._get_event_bounds(session_id)
        if event_bounds is None:
            return 0

        min_event_ms, max_event_ms = event_bounds
        first_window_end_ms = _to_window_end(min_event_ms)
        last_window_end_ms = _to_window_end(max_event_ms)
        start_window_end_ms = first_window_end_ms

        window_count = (
            (last_window_end_ms - first_window_end_ms) // WINDOW_SIZE_MS
        ) + 1
        if window_count > self._max_rebuild_windows:
            start_window_end_ms = last_window_end_ms - (
                (self._max_rebuild_windows - 1) * WINDOW_SIZE_MS
            )
            logger.warning(
                "summary_rebuild_window_count_capped session_id=%s requested=%s capped=%s",
                session_id,
                window_count,
                self._max_rebuild_windows,
            )

        for window_end_ms in range(
            start_window_end_ms, last_window_end_ms + 1, WINDOW_SIZE_MS
        ):
            existing_window = await self._get_summary_window(
                session_id=session_id,
                window_end_ms=window_end_ms,
            )
            if existing_window is not None:
                continue
            await self._build_window(
                session_id=session_id,
                window_end_ms=window_end_ms,
                persist=True,
                lang_mode=session.lang_mode,
            )
            # Release SQLite writer lock immediately per window to avoid
            # long lock retention across LLM calls in subsequent windows.
            await commit_with_retry(self._db)

        return await self._count_summary_windows(session_id)

    async def _build_window(
        self,
        *,
        session_id: str,
        window_end_ms: int,
        persist: bool,
        lang_mode: str = "ja",
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

        if not speech_events and not visual_events:
            if persist:
                await self._upsert_summary_window(
                    session_id=session_id,
                    window_start_ms=window_start_ms,
                    window_end_ms=window_end_ms,
                    summary_text="",
                    key_terms=[],
                    evidence=[],
                )
            return LectureSummaryLatestResponse(
                session_id=session_id,
                window_start_ms=window_start_ms,
                window_end_ms=window_end_ms,
                summary="",
                key_terms=[],
                evidence=[],
                status="no_data",
            )

        summary_result = await self._summary_generator.generate_summary(
            speech_events=speech_events,
            visual_events=visual_events,
            lang_mode=lang_mode,
        )
        summary_text = summary_result.summary

        # Map evidence tags from generator result to schema format
        evidence_type_map: dict[str, LectureEvidenceType] = {
            "speech": "speech",
            "slide": "slide",
            "board": "board",
        }

        key_terms: list[LectureSummaryKeyTerm] = []
        for term_item in summary_result.key_terms:
            # Extract term value (support both legacy string and new dict format)
            term_value = (
                term_item if isinstance(term_item, str) else term_item.get("term", "")
            )
            term_explanation = (
                term_item.get("explanation", "") if isinstance(term_item, dict) else ""
            )
            term_translation = (
                term_item.get("translation", "") if isinstance(term_item, dict) else ""
            )

            term_evidence_tags: list[LectureEvidenceType] = (
                self._collect_term_evidence_tags(
                    term=term_value,
                    evidence_tags=summary_result.evidence_tags,
                    evidence_type_map=evidence_type_map,
                )
            )
            # Ensure at least one evidence tag (use "speech" as default)
            if not term_evidence_tags:
                term_evidence_tags = ["speech"]
            key_terms.append(
                LectureSummaryKeyTerm(
                    term=term_value,
                    explanation=term_explanation,
                    translation=term_translation,
                    evidence_tags=term_evidence_tags,
                )
            )
        evidence = self._build_evidence(
            speech_events=speech_events,
            visual_events=visual_events,
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
        user_id_candidates = get_user_id_candidates(user_id)
        result = await self._db.execute(
            select(LectureSession).where(
                LectureSession.id == session_id,
                LectureSession.user_id.in_(user_id_candidates),
            )
        )
        session = result.scalar_one_or_none()

        if session is None:
            raise LectureSessionNotFoundError(
                f"lecture session not found: {session_id}"
            )
        if session.status not in SUMMARY_ALLOWED_SESSION_STATUSES:
            raise LectureSessionInactiveError(
                f"lecture session state does not allow summary: {session.status}"
            )
        return session

    async def _get_event_bounds(self, session_id: str) -> tuple[int, int] | None:
        speech_result = await self._db.execute(
            select(
                func.min(SpeechEvent.start_ms),
                func.max(SpeechEvent.end_ms),
            ).where(
                SpeechEvent.session_id == session_id,
                SpeechEvent.is_final == True,  # noqa: E712
            )
        )
        speech_min, speech_max = speech_result.one()
        visual_result = await self._db.execute(
            select(
                func.min(VisualEvent.timestamp_ms),
                func.max(VisualEvent.timestamp_ms),
            ).where(VisualEvent.session_id == session_id)
        )
        visual_min, visual_max = visual_result.one()

        min_candidates = [
            value for value in [speech_min, visual_min] if isinstance(value, int)
        ]
        max_candidates = [
            value for value in [speech_max, visual_max] if isinstance(value, int)
        ]
        if not min_candidates or not max_candidates:
            return None
        return min(min_candidates), max(max_candidates)

    async def _get_max_event_ms(self, session_id: str) -> int | None:
        event_bounds = await self._get_event_bounds(session_id)
        if event_bounds is None:
            return None
        _, max_event_ms = event_bounds
        return max_event_ms

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
        result = await self._db.execute(
            select(SummaryWindow).where(
                SummaryWindow.session_id == session_id,
                SummaryWindow.start_ms == window_start_ms,
                SummaryWindow.end_ms == window_end_ms,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            self._db.add(
                SummaryWindow(
                    session_id=session_id,
                    start_ms=window_start_ms,
                    end_ms=window_end_ms,
                    summary_text=summary_text,
                    key_terms_json=key_terms_json,
                    evidence_event_ids_json=evidence_refs,
                )
            )
        else:
            existing.summary_text = summary_text
            existing.key_terms_json = key_terms_json
            existing.evidence_event_ids_json = evidence_refs

        for attempt in range(WRITE_RETRY_ATTEMPTS):
            try:
                await self._db.flush()
                return
            except OperationalError as exc:
                if (
                    not is_sqlite_locked_error(exc)
                    or attempt >= WRITE_RETRY_ATTEMPTS - 1
                ):
                    raise
                await self._db.rollback()
                delay = WRITE_RETRY_BASE_DELAY_SECONDS * (2**attempt)
                await asyncio.sleep(delay)

    async def _get_summary_window(
        self,
        *,
        session_id: str,
        window_end_ms: int,
    ) -> SummaryWindow | None:
        result = await self._db.execute(
            select(SummaryWindow).where(
                SummaryWindow.session_id == session_id,
                SummaryWindow.end_ms == window_end_ms,
            )
        )
        return result.scalar_one_or_none()

    async def _count_summary_windows(self, session_id: str) -> int:
        result = await self._db.execute(
            select(func.count(SummaryWindow.id)).where(
                SummaryWindow.session_id == session_id
            )
        )
        count = result.scalar_one()
        return int(count)

    @staticmethod
    def _response_from_summary_window(
        summary_window: SummaryWindow,
    ) -> LectureSummaryLatestResponse:
        key_terms: list[LectureSummaryKeyTerm] = []
        for raw_term in summary_window.key_terms_json or []:
            if isinstance(raw_term, str):
                normalized_term = raw_term.strip()
                if not normalized_term:
                    continue
                key_terms.append(
                    LectureSummaryKeyTerm(
                        term=normalized_term,
                        explanation="",
                        translation="",
                        evidence_tags=["speech"],
                    )
                )
                continue
            if not isinstance(raw_term, dict):
                continue
            term_value = raw_term.get("term", "")
            if not isinstance(term_value, str) or not term_value.strip():
                continue
            evidence_tags_raw = raw_term.get("evidence_tags", ["speech"])
            if (
                not isinstance(evidence_tags_raw, list)
                or not evidence_tags_raw
                or any(
                    tag not in EVIDENCE_TAG_ORDER
                    for tag in evidence_tags_raw
                    if isinstance(tag, str)
                )
            ):
                evidence_tags: list[LectureEvidenceType] = ["speech"]
            else:
                evidence_tags = [
                    tag for tag in evidence_tags_raw if isinstance(tag, str)
                ][:MAX_KEY_TERM_EVIDENCE_TAGS]
            key_terms.append(
                LectureSummaryKeyTerm(
                    term=term_value.strip(),
                    explanation=str(raw_term.get("explanation", "")),
                    translation=str(raw_term.get("translation", "")),
                    evidence_tags=evidence_tags or ["speech"],
                )
            )

        evidence: list[LectureSummaryEvidence] = []
        for raw_ref in summary_window.evidence_event_ids_json or []:
            if not isinstance(raw_ref, str) or ":" not in raw_ref:
                continue
            raw_type, ref_id = raw_ref.split(":", 1)
            if raw_type not in EVIDENCE_TAG_ORDER or not ref_id:
                continue
            evidence.append(
                LectureSummaryEvidence(
                    type=raw_type,
                    ref_id=ref_id,
                )
            )

        return LectureSummaryLatestResponse(
            session_id=summary_window.session_id,
            window_start_ms=summary_window.start_ms,
            window_end_ms=summary_window.end_ms,
            summary=summary_window.summary_text,
            key_terms=key_terms,
            evidence=evidence,
            status="ok" if evidence else "no_data",
        )

    @staticmethod
    def _collect_term_evidence_tags(
        *,
        term: str,
        evidence_tags: list[dict[str, str]],
        evidence_type_map: dict[str, LectureEvidenceType],
    ) -> list[LectureEvidenceType]:
        tags: list[LectureEvidenceType] = []
        for tag in evidence_tags:
            if term not in tag.get("text", ""):
                continue

            evidence_type = evidence_type_map.get(tag.get("type", ""))
            if evidence_type is None or evidence_type in tags:
                continue

            tags.append(evidence_type)
            if len(tags) >= MAX_KEY_TERM_EVIDENCE_TAGS:
                break
        return tags

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

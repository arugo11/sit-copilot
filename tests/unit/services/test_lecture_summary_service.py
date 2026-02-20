"""Unit tests for lecture summary service."""

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.summary_window import SummaryWindow
from app.models.visual_event import VisualEvent
from app.services.lecture_live_service import LectureSessionNotFoundError
from app.services.lecture_summary_service import SqlAlchemyLectureSummaryService


@pytest.mark.asyncio
async def test_get_latest_summary_persists_window_for_active_session(
    db_session: AsyncSession,
) -> None:
    """Latest summary should persist a summary window with evidence."""
    session = LectureSession(
        id="lec_summary_001",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="active",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    db_session.add(
        SpeechEvent(
            session_id=session.id,
            start_ms=15000,
            end_ms=28000,
            text="外れ値は散布図で先に確認します。",
            confidence=0.95,
            is_final=True,
            speaker="teacher",
        )
    )
    db_session.add(
        VisualEvent(
            session_id=session.id,
            timestamp_ms=27000,
            source="board",
            ocr_text="外れ値, 残差確認",
            ocr_confidence=0.82,
            quality="good",
            change_score=0.44,
            blob_path=None,
        )
    )
    await db_session.flush()

    service = SqlAlchemyLectureSummaryService(db_session)
    response = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
    )

    assert response.status == "ok"
    assert response.window_end_ms >= 30000
    assert len(response.evidence) >= 1

    result = await db_session.execute(
        select(SummaryWindow).where(SummaryWindow.session_id == session.id)
    )
    summary_window = result.scalar_one_or_none()
    assert summary_window is not None
    assert summary_window.summary_text != ""


@pytest.mark.asyncio
async def test_get_latest_summary_returns_no_data_when_no_events(
    db_session: AsyncSession,
) -> None:
    """Latest summary should return no_data when session has no events."""
    session = LectureSession(
        id="lec_summary_002",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="active",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    await db_session.flush()

    service = SqlAlchemyLectureSummaryService(db_session)
    response = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
    )

    assert response.status == "no_data"
    assert response.window_end_ms == 0
    assert response.evidence == []


@pytest.mark.asyncio
async def test_rebuild_windows_creates_window_per_30_seconds(
    db_session: AsyncSession,
) -> None:
    """Rebuild should create all windows up to latest event timestamp."""
    session = LectureSession(
        id="lec_summary_003",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="active",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    db_session.add(
        SpeechEvent(
            session_id=session.id,
            start_ms=10000,
            end_ms=11000,
            text="序盤の説明です。",
            confidence=0.94,
            is_final=True,
            speaker="teacher",
        )
    )
    db_session.add(
        SpeechEvent(
            session_id=session.id,
            start_ms=62000,
            end_ms=65000,
            text="終盤の説明です。",
            confidence=0.92,
            is_final=True,
            speaker="teacher",
        )
    )
    await db_session.flush()

    service = SqlAlchemyLectureSummaryService(db_session)
    count = await service.rebuild_windows(
        session_id=session.id,
        user_id="demo_user",
    )

    assert count == 3


@pytest.mark.asyncio
async def test_summary_rejects_other_user_session(
    db_session: AsyncSession,
) -> None:
    """Summary service should reject sessions owned by another user."""
    session = LectureSession(
        id="lec_summary_004",
        user_id="owner_a",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="active",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    await db_session.flush()

    service = SqlAlchemyLectureSummaryService(db_session)
    with pytest.raises(LectureSessionNotFoundError):
        await service.get_latest_summary(
            session_id=session.id,
            user_id="owner_b",
        )


@pytest.mark.asyncio
async def test_get_latest_summary_is_safe_under_concurrent_requests(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Concurrent summary requests should not raise conflict errors."""
    session = LectureSession(
        id="lec_summary_005",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="active",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    db_session.add(
        SpeechEvent(
            session_id=session.id,
            start_ms=15000,
            end_ms=28000,
            text="外れ値は散布図で先に確認します。",
            confidence=0.95,
            is_final=True,
            speaker="teacher",
        )
    )
    await db_session.flush()

    async def _request_summary() -> None:
        async with session_factory() as concurrent_session:
            service = SqlAlchemyLectureSummaryService(concurrent_session)
            await service.get_latest_summary(
                session_id=session.id,
                user_id="demo_user",
            )
            await concurrent_session.commit()

    await asyncio.gather(_request_summary(), _request_summary())

    result = await db_session.execute(
        select(SummaryWindow).where(SummaryWindow.session_id == session.id)
    )
    summary_windows = result.scalars().all()
    assert len(summary_windows) == 1

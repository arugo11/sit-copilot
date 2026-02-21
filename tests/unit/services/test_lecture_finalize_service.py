"""Unit tests for lecture finalize service."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_chunk import LectureChunk
from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.visual_event import VisualEvent
from app.schemas.lecture_qa import LectureIndexBuildResponse
from app.services.lecture_finalize_service import (
    LectureSessionStateError,
    SqlAlchemyLectureFinalizeService,
)
from app.services.lecture_live_service import LectureSessionNotFoundError
from app.services.lecture_summary_service import SqlAlchemyLectureSummaryService


@pytest.fixture
def mock_summary_generator():
    """Mock summary generator for finalize tests."""
    from app.services.lecture_summary_generator_service import LectureSummaryResult

    class MockGenerator:
        async def generate_summary(self, speech_events, visual_events, lang_mode):
            return LectureSummaryResult(
                summary="Mock summary",
                key_terms=["test"],
                evidence_tags=[
                    {"type": "speech", "timestamp": "00:00", "text": "test"}
                ],
            )

    return MockGenerator()


class SuccessfulIndexService:
    """Stub index service that always succeeds."""

    async def build_index(
        self,
        session_id: str,
        user_id: str,
        rebuild: bool,
    ) -> LectureIndexBuildResponse:
        _ = (session_id, user_id, rebuild)
        return LectureIndexBuildResponse(
            index_version="v1",
            chunk_count=1,
            built_at=datetime.now(UTC),
            status="success",
        )


class FailingIndexService:
    """Stub index service that always fails."""

    async def build_index(
        self,
        session_id: str,
        user_id: str,
        rebuild: bool,
    ) -> LectureIndexBuildResponse:
        _ = (session_id, user_id, rebuild)
        raise RuntimeError("index build failed")


@pytest.mark.asyncio
async def test_finalize_active_session_generates_artifacts(
    db_session: AsyncSession,
    mock_summary_generator,
) -> None:
    """Finalize should create summary/chunk artifacts and mark session finalized."""
    session = LectureSession(
        id="lec_finalize_001",
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
            start_ms=12000,
            end_ms=19000,
            text="外れ値の確認手順を説明します。",
            confidence=0.95,
            is_final=True,
            speaker="teacher",
        )
    )
    db_session.add(
        VisualEvent(
            session_id=session.id,
            timestamp_ms=18000,
            source="slide",
            ocr_text="外れ値, 残差",
            ocr_confidence=0.81,
            quality="good",
            change_score=0.31,
            blob_path=None,
        )
    )
    await db_session.flush()

    summary_service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    service = SqlAlchemyLectureFinalizeService(
        db=db_session,
        user_id="demo_user",
        summary_service=summary_service,
        index_service=SuccessfulIndexService(),
    )

    response = await service.finalize(
        session_id=session.id,
        build_qa_index=True,
    )

    assert response.status == "finalized"
    assert response.qa_index_built is True
    assert response.stats.speech_events == 1
    assert response.stats.visual_events == 1
    assert response.stats.summary_windows >= 1
    assert response.stats.lecture_chunks >= 2

    session_result = await db_session.execute(
        select(LectureSession).where(LectureSession.id == session.id)
    )
    finalized = session_result.scalar_one()
    assert finalized.status == "finalized"
    assert finalized.ended_at is not None

    chunk_result = await db_session.execute(
        select(LectureChunk).where(LectureChunk.session_id == session.id)
    )
    assert len(chunk_result.scalars().all()) == response.stats.lecture_chunks


@pytest.mark.asyncio
async def test_finalize_is_idempotent_for_finalized_session(
    db_session: AsyncSession,
    mock_summary_generator,
) -> None:
    """Repeated finalize should not duplicate lecture chunks."""
    session = LectureSession(
        id="lec_finalize_002",
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
            start_ms=12000,
            end_ms=19000,
            text="再実行テスト用イベント。",
            confidence=0.95,
            is_final=True,
            speaker="teacher",
        )
    )
    await db_session.flush()

    summary_service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    service = SqlAlchemyLectureFinalizeService(
        db=db_session,
        user_id="demo_user",
        summary_service=summary_service,
        index_service=SuccessfulIndexService(),
    )

    first = await service.finalize(session_id=session.id, build_qa_index=False)
    second = await service.finalize(session_id=session.id, build_qa_index=False)

    assert first.status == "finalized"
    assert second.status == "finalized"
    assert second.stats.lecture_chunks == first.stats.lecture_chunks


@pytest.mark.asyncio
async def test_finalize_unknown_session_raises_not_found(
    db_session: AsyncSession,
    mock_summary_generator,
) -> None:
    """Finalize should reject unknown sessions."""
    summary_service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    service = SqlAlchemyLectureFinalizeService(
        db=db_session,
        user_id="demo_user",
        summary_service=summary_service,
        index_service=SuccessfulIndexService(),
    )

    with pytest.raises(LectureSessionNotFoundError):
        await service.finalize(session_id="lec_missing", build_qa_index=False)


@pytest.mark.asyncio
async def test_finalize_rejects_error_status_session(
    db_session: AsyncSession,
    mock_summary_generator,
) -> None:
    """Finalize should reject sessions in error status."""
    session = LectureSession(
        id="lec_finalize_003",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="error",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    await db_session.flush()

    summary_service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    service = SqlAlchemyLectureFinalizeService(
        db=db_session,
        user_id="demo_user",
        summary_service=summary_service,
        index_service=SuccessfulIndexService(),
    )

    with pytest.raises(LectureSessionStateError):
        await service.finalize(session_id=session.id, build_qa_index=False)


@pytest.mark.asyncio
async def test_finalize_handles_index_failure_as_false_flag(
    db_session: AsyncSession,
    mock_summary_generator,
) -> None:
    """Finalize should continue when optional index build fails."""
    session = LectureSession(
        id="lec_finalize_004",
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
            start_ms=1000,
            end_ms=7000,
            text="指数関数の説明。",
            confidence=0.9,
            is_final=True,
            speaker="teacher",
        )
    )
    await db_session.flush()

    summary_service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    service = SqlAlchemyLectureFinalizeService(
        db=db_session,
        user_id="demo_user",
        summary_service=summary_service,
        index_service=FailingIndexService(),
    )

    response = await service.finalize(
        session_id=session.id,
        build_qa_index=True,
    )

    assert response.status == "finalized"
    assert response.qa_index_built is False


@pytest.mark.asyncio
async def test_finalize_keeps_existing_qa_index_true_when_rebuild_fails(
    db_session: AsyncSession,
    mock_summary_generator,
) -> None:
    """Finalize should not regress qa_index_built from true to false."""
    session = LectureSession(
        id="lec_finalize_005",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="finalized",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
        qa_index_built=True,
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    await db_session.flush()

    summary_service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    service = SqlAlchemyLectureFinalizeService(
        db=db_session,
        user_id="demo_user",
        summary_service=summary_service,
        index_service=FailingIndexService(),
    )

    response = await service.finalize(
        session_id=session.id,
        build_qa_index=True,
    )

    assert response.status == "finalized"
    assert response.qa_index_built is True

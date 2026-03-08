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
from app.services.lecture_live_service import (
    LectureSessionInactiveError,
    LectureSessionNotFoundError,
)
from app.services.lecture_summary_generator_service import (
    LectureSummaryResult,
)
from app.services.lecture_summary_service import SqlAlchemyLectureSummaryService


@pytest.fixture
def mock_summary_generator():
    """Mock summary generator for unit tests."""
    return MockLectureSummaryGeneratorService()


class MockLectureSummaryGeneratorService:
    """Mock implementation of LectureSummaryGeneratorService for testing."""

    def __init__(
        self,
        summary: str = "Mock Azure OpenAI summary",
        key_terms: list[str] | None = None,
        evidence_tags: list[dict[str, str]] | None = None,
        should_fail: bool = False,
    ) -> None:
        self._summary = summary
        self._key_terms = key_terms or ["モックキーワード"]
        self._evidence_tags = evidence_tags or [
            {"type": "speech", "timestamp": "00:15", "text": "Mock evidence"}
        ]
        self._should_fail = should_fail
        self.call_count = 0
        self.received_lang_modes: list[str] = []

    async def generate_summary(
        self,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
        lang_mode: str,
    ) -> LectureSummaryResult:
        """Generate mock summary."""
        self.call_count += 1
        self.received_lang_modes.append(lang_mode)
        if self._should_fail:
            raise RuntimeError("Mock generator error")
        return LectureSummaryResult(
            summary=self._summary,
            key_terms=self._key_terms,
            evidence_tags=self._evidence_tags,
        )


@pytest.mark.asyncio
async def test_get_latest_summary_persists_window_for_active_session(
    db_session: AsyncSession,
    mock_summary_generator: MockLectureSummaryGeneratorService,
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

    service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
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
    mock_summary_generator: MockLectureSummaryGeneratorService,
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

    service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    response = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
    )

    assert response.status == "no_data"
    assert response.window_end_ms == 0
    assert response.evidence == []


@pytest.mark.asyncio
async def test_get_latest_summary_reuses_cached_window_until_force_rebuild(
    db_session: AsyncSession,
    mock_summary_generator: MockLectureSummaryGeneratorService,
) -> None:
    """Cached summary windows should prevent duplicate generation by default."""
    session = LectureSession(
        id="lec_summary_cache_001",
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
            end_ms=5000,
            text="最初の説明です。",
            confidence=0.95,
            is_final=True,
            speaker="teacher",
        )
    )
    await db_session.flush()

    service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )

    first = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
    )
    second = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
    )
    rebuilt = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
        force_rebuild=True,
    )

    assert first.status == "ok"
    assert second.status == "ok"
    assert rebuilt.status == "ok"
    assert mock_summary_generator.call_count == 2
    assert first.summary == second.summary == rebuilt.summary


@pytest.mark.asyncio
async def test_rebuild_windows_creates_window_per_30_seconds(
    db_session: AsyncSession,
    mock_summary_generator: MockLectureSummaryGeneratorService,
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

    service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    count = await service.rebuild_windows(
        session_id=session.id,
        user_id="demo_user",
    )

    assert count == 3


@pytest.mark.asyncio
async def test_summary_rejects_other_user_session(
    db_session: AsyncSession,
    mock_summary_generator: MockLectureSummaryGeneratorService,
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

    service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    with pytest.raises(LectureSessionNotFoundError):
        await service.get_latest_summary(
            session_id=session.id,
            user_id="owner_b",
        )


@pytest.mark.asyncio
async def test_summary_rejects_inactive_session(
    db_session: AsyncSession,
    mock_summary_generator: MockLectureSummaryGeneratorService,
) -> None:
    """Summary service should reject inactive lecture sessions."""
    session = LectureSession(
        id="lec_summary_004_inactive",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="inactive",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    await db_session.flush()

    service = SqlAlchemyLectureSummaryService(
        db_session, summary_generator=mock_summary_generator
    )
    with pytest.raises(LectureSessionInactiveError):
        await service.get_latest_summary(
            session_id=session.id,
            user_id="demo_user",
        )

    assert mock_summary_generator.call_count == 0


@pytest.mark.asyncio
async def test_get_latest_summary_is_safe_under_concurrent_requests(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_summary_generator: MockLectureSummaryGeneratorService,
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
            service = SqlAlchemyLectureSummaryService(
                concurrent_session, summary_generator=mock_summary_generator
            )
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


# ============================================================================
# LLM Generator Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_latest_summary_with_llm_generator_uses_generated_summary(
    db_session: AsyncSession,
) -> None:
    """Service should use LLM generator when provided."""
    session = LectureSession(
        id="lec_llm_001",
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
            id="speech_llm_001",
            session_id=session.id,
            start_ms=15000,
            end_ms=22000,
            text="外れ値の確認手順を説明します。",
            confidence=0.93,
            is_final=True,
            speaker="teacher",
        )
    )
    db_session.add(
        VisualEvent(
            id="visual_llm_001",
            session_id=session.id,
            timestamp_ms=18000,
            source="slide",
            ocr_text="外れ値, 残差確認",
            ocr_confidence=0.82,
            quality="good",
            change_score=0.44,
            blob_path=None,
        )
    )
    await db_session.flush()

    mock_generator = MockLectureSummaryGeneratorService(
        summary="Azure OpenAI で生成された要約テキスト",
        key_terms=["外れ値", "残差", "散布図"],
    )

    service = SqlAlchemyLectureSummaryService(
        db_session,
        summary_generator=mock_generator,
    )
    response = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
    )

    assert response.status == "ok"
    assert response.summary == "Azure OpenAI で生成された要約テキスト"
    assert len(response.key_terms) == 3
    assert "外れ値" in [t.term for t in response.key_terms]
    assert mock_generator.call_count == 1
    assert mock_generator.received_lang_modes == ["ja"]


@pytest.mark.asyncio
async def test_get_latest_summary_with_llm_generator_passes_en_lang_mode(
    db_session: AsyncSession,
) -> None:
    """Service should pass session lang_mode=en to summary generator."""
    session = LectureSession(
        id="lec_llm_en_001",
        user_id="demo_user",
        course_id=None,
        course_name="Statistics 101",
        lang_mode="en",
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
            id="speech_llm_en_001",
            session_id=session.id,
            start_ms=15000,
            end_ms=22000,
            text="Check outliers using a scatter plot.",
            confidence=0.93,
            is_final=True,
            speaker="teacher",
        )
    )
    await db_session.flush()

    mock_generator = MockLectureSummaryGeneratorService(
        summary="English summary from Azure OpenAI",
        key_terms=["outlier", "scatter plot"],
    )

    service = SqlAlchemyLectureSummaryService(
        db_session,
        summary_generator=mock_generator,
    )
    response = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
    )

    assert response.status == "ok"
    assert response.summary == "English summary from Azure OpenAI"
    assert mock_generator.received_lang_modes == ["en"]


@pytest.mark.asyncio
async def test_get_latest_summary_propagates_generator_error(
    db_session: AsyncSession,
) -> None:
    """Generator error should propagate when LLM generator fails."""
    session = LectureSession(
        id="lec_llm_002",
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
            id="speech_llm_002",
            session_id=session.id,
            start_ms=15000,
            end_ms=22000,
            text="テストテキスト",
            confidence=0.93,
            is_final=True,
            speaker="teacher",
        )
    )
    await db_session.flush()

    mock_generator = MockLectureSummaryGeneratorService(should_fail=True)

    service = SqlAlchemyLectureSummaryService(
        db_session,
        summary_generator=mock_generator,
    )

    with pytest.raises(RuntimeError, match="Mock generator error"):
        await service.get_latest_summary(
            session_id=session.id,
            user_id="demo_user",
        )


@pytest.mark.asyncio
async def test_summary_with_llm_generator_still_enforces_ownership(
    db_session: AsyncSession,
) -> None:
    """LLM generator should not bypass ownership checks."""
    session = LectureSession(
        id="lec_llm_003",
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

    mock_generator = MockLectureSummaryGeneratorService()

    service = SqlAlchemyLectureSummaryService(
        db_session,
        summary_generator=mock_generator,
    )

    with pytest.raises(LectureSessionNotFoundError):
        await service.get_latest_summary(
            session_id=session.id,
            user_id="owner_b",
        )

    # Generator should not have been called due to early ownership check
    assert mock_generator.call_count == 0


@pytest.mark.asyncio
async def test_summary_with_llm_generator_returns_no_data_when_no_events(
    db_session: AsyncSession,
) -> None:
    """LLM generator service should return no_data when session has no events."""
    session = LectureSession(
        id="lec_llm_004",
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

    mock_generator = MockLectureSummaryGeneratorService()

    service = SqlAlchemyLectureSummaryService(
        db_session,
        summary_generator=mock_generator,
    )
    response = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
    )

    assert response.status == "no_data"
    assert response.window_end_ms == 0
    assert response.evidence == []

    # Generator should not have been called when there are no events
    assert mock_generator.call_count == 0


@pytest.mark.asyncio
async def test_summary_key_term_evidence_tags_are_deduped_and_capped(
    db_session: AsyncSession,
) -> None:
    """Key-term evidence tags should be unique and capped at schema max."""
    session = LectureSession(
        id="lec_llm_005",
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
            id="speech_llm_005",
            session_id=session.id,
            start_ms=10000,
            end_ms=15000,
            text="外れ値の説明",
            confidence=0.93,
            is_final=True,
            speaker="teacher",
        )
    )
    await db_session.flush()

    mock_generator = MockLectureSummaryGeneratorService(
        summary="要約",
        key_terms=["外れ値"],
        evidence_tags=[
            {"type": "speech", "timestamp": "00:10", "text": "外れ値の説明"},
            {"type": "slide", "timestamp": "00:12", "text": "外れ値の図"},
            {"type": "board", "timestamp": "00:13", "text": "外れ値の式"},
            {"type": "speech", "timestamp": "00:14", "text": "外れ値の補足"},
            {"type": "slide", "timestamp": "00:15", "text": "外れ値の例"},
        ],
    )

    service = SqlAlchemyLectureSummaryService(
        db_session,
        summary_generator=mock_generator,
    )
    response = await service.get_latest_summary(
        session_id=session.id,
        user_id="demo_user",
    )

    assert response.status == "ok"
    assert len(response.key_terms) == 1
    assert response.key_terms[0].evidence_tags == ["speech", "slide", "board"]

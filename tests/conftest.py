"""Pytest configuration and fixtures."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import (  # noqa: F401  # Ensure model metadata is loaded
    LectureChunk,
    LectureSession,
    QATurn,
    SpeechEvent,
    SummaryWindow,
    User,
    UserSettings,
    VisualEvent,
)
from app.services.lecture_summary_generator_service import (
    LectureSummaryGeneratorService,
    LectureSummaryResult,
)


@pytest.fixture(autouse=True)
def enable_live_features_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep legacy integration tests exercising feature-on paths.

    Production defaults remain fail-closed; tests opt back into the relevant
    endpoints unless a test explicitly overrides them.
    """

    monkeypatch.setattr(settings, "azure_openai_enabled", True)
    monkeypatch.setattr(settings, "lecture_live_asr_review_enabled", True)
    monkeypatch.setattr(settings, "lecture_live_translation_enabled", True)
    monkeypatch.setattr(settings, "lecture_live_summary_enabled", True)
    monkeypatch.setattr(settings, "lecture_live_keyterms_enabled", True)
    monkeypatch.setattr(settings, "lecture_qa_enabled", True)
    monkeypatch.setattr(settings, "azure_search_enabled", False)


@pytest.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    """Create an in-memory SQLite engine shared across async sessions."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the test engine."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """Provide a database session for unit tests."""
    async with session_factory() as session:
        yield session


@pytest.fixture
async def async_client(
    session_factory: async_sessionmaker[AsyncSession],
    mock_summary_generator: MagicMock,
) -> AsyncGenerator[AsyncClient]:
    """Async client for testing FastAPI endpoints.

    Uses ASGITransport for modern FastAPI async testing (2025 best practice).
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Import here to avoid circular dependency
    from app.api.v4.lecture import (
        get_caption_transform_service,
        get_lecture_summary_service,
    )
    from app.services.lecture_summary_service import SqlAlchemyLectureSummaryService
    from app.services.live_caption_transform_service import CaptionTransformResult

    def override_summary_service():
        return SqlAlchemyLectureSummaryService(
            db=session_factory(),
            summary_generator=mock_summary_generator,
        )

    class FakeCaptionTransformService:
        async def transform(
            self,
            text: str,
            target_lang_mode: str,
        ) -> CaptionTransformResult:
            if target_lang_mode == "ja":
                return CaptionTransformResult(
                    text=text.strip(),
                    status="passthrough",
                    fallback_reason=None,
                )
            if target_lang_mode == "en":
                return CaptionTransformResult(
                    text=f"EN: {text.strip()}",
                    status="translated",
                    fallback_reason=None,
                )
            return CaptionTransformResult(
                text=f"やさしい: {text.strip()}",
                status="translated",
                fallback_reason=None,
            )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_lecture_summary_service] = override_summary_service
    app.dependency_overrides[get_caption_transform_service] = (
        FakeCaptionTransformService
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_summary_generator() -> LectureSummaryGeneratorService:
    """Mock Azure OpenAI summary generator for testing."""
    mock = MagicMock(spec=LectureSummaryGeneratorService)

    async def _generate_summary(speech_events, visual_events, lang_mode):
        # Return deterministic mock summary
        speech_text = " ".join([se.text for se in speech_events if se.is_final])
        visual_text = " ".join([ve.ocr_text for ve in visual_events if ve.ocr_text])

        summary_parts = []
        if speech_text:
            summary_parts.append(f"この区間では、{speech_text}")
        if visual_text:
            summary_parts.append(f"視覚情報として {visual_text} が確認されました。")

        summary = (
            " ".join(summary_parts)
            if summary_parts
            else "この区間の要約を生成できるデータがありません。"
        )

        # Truncate to 600 chars
        if len(summary) > 600:
            summary = summary[:596] + "..."

        # Build evidence tags (always at least one)
        evidence_tags = []
        if speech_text:
            evidence_tags.append(
                {"type": "speech", "timestamp": "00:15", "text": speech_text[:50]}
            )
        if visual_text:
            evidence_tags.append(
                {"type": "visual", "timestamp": "00:20", "text": visual_text[:50]}
            )
        if not evidence_tags:
            evidence_tags.append(
                {"type": "speech", "timestamp": "00:00", "text": "要約データなし"}
            )

        return LectureSummaryResult(
            summary=summary,
            key_terms=["テスト用語"],
            evidence_tags=evidence_tags,
        )

    mock.generate_summary = AsyncMock(side_effect=_generate_summary)
    return mock

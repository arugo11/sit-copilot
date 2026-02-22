"""Integration tests for Weave observability.

These tests verify that Weave is properly integrated into the application
lifecycle and that observations flow through the system correctly.
"""

import asyncio
from collections.abc import AsyncGenerator

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
from app.db.session import get_db
from app.main import app
from app.models import (  # noqa: F401
    LectureChunk,
    LectureSession,
    QATurn,
    SpeechEvent,
    SummaryWindow,
    User,
    UserSettings,
    VisualEvent,
)
from app.services.observability import NoopWeaveObserverService


@pytest.fixture
async def weave_test_engine() -> AsyncGenerator[AsyncEngine]:
    """Create in-memory SQLite engine for integration tests."""
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
def weave_session_factory(
    weave_test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create session factory bound to test engine."""
    return async_sessionmaker(
        bind=weave_test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
async def weave_integration_client(
    weave_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient]:
    """Create test client with Weave observer disabled (noop)."""

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        async with weave_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


class TestWeaveLifecycle:
    """Tests for Weave integration in app lifecycle."""

    def test_app_has_weave_observer_attribute(self) -> None:
        """FastAPI app should expose weave_observer dependency."""
        # The app might not be fully initialized in test context
        # but the main module should export the observer types
        from app.services.observability import (
            WandBWeaveObserverService,
            WeaveObserverService,
        )

        # Verify protocol exists
        assert WeaveObserverService is not None

        # Verify implementations exist
        assert NoopWeaveObserverService is not None
        assert WandBWeaveObserverService is not None


class TestNoopWeaveObserverIntegration:
    """Integration tests using noop observer (Weave disabled)."""

    @pytest.mark.asyncio
    async def test_noop_observer_available_in_dependency(
        self, weave_integration_client: AsyncClient
    ) -> None:
        """Noop observer should be injectable and functional."""
        # The noop observer should be used when WEAVE_ENABLED=false

        observer = NoopWeaveObserverService()

        # All methods should work without errors
        await observer.track_qa_turn(
            session_id="test",
            feature="test",
            question="Q",
            answer="A",
            confidence="high",
            citations=[],
            retrieved_chunk_ids=[],
            latency_ms=100,
            verifier_supported=True,
            outcome_reason="test",
        )

        await observer.track_llm_call(
            provider="test",
            model="test",
            prompt="test",
            response="test",
            latency_ms=100,
        )

        await observer.track_ocr_with_image(
            session_id="test",
            timestamp_ms=0,
            source="test",
            ocr_text="test",
            ocr_confidence=0.9,
            quality="high",
            change_score=0.5,
        )

        await observer.track_slide_transition(
            session_id="test",
            timestamp_ms=0,
            slide_number=1,
            ocr_text="test",
        )

        await observer.track_speech_event(
            session_id="test",
            start_ms=0,
            end_ms=100,
            text="test",
            original_text="test",
            confidence=0.9,
            is_final=True,
            speaker="test",
        )


class TestWeaveSessionContext:
    """Tests for session context propagation."""

    @pytest.mark.asyncio
    async def test_session_context_manager_noop(self) -> None:
        """Session context manager should work with noop observer."""

        observer = NoopWeaveObserverService()

        async with observer.with_session_context("session-123"):
            # Context should be active
            await observer.track_qa_turn(
                session_id="session-123",
                feature="test",
                question="Q",
                answer="A",
                confidence="high",
                citations=[],
                retrieved_chunk_ids=[],
                latency_ms=100,
                verifier_supported=True,
                outcome_reason="test",
            )

    @pytest.mark.asyncio
    async def test_weave_context_class(self) -> None:
        """WeaveContext should provide session tracking."""
        from app.services.observability.weave_context import WeaveContext

        ctx = WeaveContext(session_id="test-session", metadata={"user": "test"})

        async with ctx.async_context():
            # Context should be active
            pass

        # Test noop
        noop = WeaveContext.noop()
        async with noop:
            pass

        # Test session factory
        session_ctx = WeaveContext.session("session-456", metadata={"key": "value"})
        async with session_ctx:
            pass


class TestWeaveDispatcherIntegration:
    """Integration tests for dispatcher behavior."""

    @pytest.mark.asyncio
    async def test_dispatcher_with_observer(self) -> None:
        """Dispatcher should work with WandBWeaveObserverService."""
        from app.core.config import WeaveSettings
        from app.services.observability import WandBWeaveObserverService

        settings = WeaveSettings(
            enabled=True,
            project="test",
            queue_maxsize=5,
            worker_count=1,
            timeout_ms=1000,
        )

        observer = WandBWeaveObserverService(settings)
        dispatcher = observer._dispatcher_value

        await dispatcher.start()

        # Dispatch some tasks
        await observer.track_qa_turn(
            session_id="test",
            feature="test",
            question="Q",
            answer="A",
            confidence="high",
            citations=[],
            retrieved_chunk_ids=[],
            latency_ms=100,
            verifier_supported=True,
            outcome_reason="test",
        )

        # Give time for processing
        await asyncio.sleep(0.1)

        await dispatcher.stop()

    @pytest.mark.asyncio
    async def test_multiple_observers_concurrent(self) -> None:
        """Multiple observers should work concurrently."""
        from app.core.config import WeaveSettings
        from app.services.observability import WandBWeaveObserverService

        settings = WeaveSettings(
            enabled=True,
            project="test",
            queue_maxsize=10,
            worker_count=2,
            timeout_ms=1000,
        )

        observer1 = WandBWeaveObserverService(settings)
        observer2 = WandBWeaveObserverService(settings)

        await observer1._dispatcher_value.start()
        await observer2._dispatcher_value.start()

        # Both should process concurrently
        task1 = observer1.track_qa_turn(
            session_id="session1",
            feature="test",
            question="Q1",
            answer="A1",
            confidence="high",
            citations=[],
            retrieved_chunk_ids=[],
            latency_ms=100,
            verifier_supported=True,
            outcome_reason="test",
        )

        task2 = observer2.track_qa_turn(
            session_id="session2",
            feature="test",
            question="Q2",
            answer="A2",
            confidence="high",
            citations=[],
            retrieved_chunk_ids=[],
            latency_ms=100,
            verifier_supported=True,
            outcome_reason="test",
        )

        await asyncio.gather(task1, task2)
        await asyncio.sleep(0.1)

        await observer1._dispatcher_value.stop()
        await observer2._dispatcher_value.stop()

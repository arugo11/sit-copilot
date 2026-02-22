"""Unit tests for Weave observer service."""

import asyncio

import pytest

from app.core.config import WeaveSettings
from app.services.observability import (
    NoopWeaveObserverService,
    WandBWeaveObserverService,
)


class TestNoopWeaveObserverService:
    """Tests for NoopWeaveObserverService."""

    @pytest.fixture
    def noop_observer(self) -> NoopWeaveObserverService:
        """Create a noop observer instance."""
        return NoopWeaveObserverService()

    @pytest.mark.asyncio
    async def test_track_qa_turn_noop(
        self, noop_observer: NoopWeaveObserverService
    ) -> None:
        """track_qa_turn should do nothing and not raise."""
        # Should not raise
        await noop_observer.track_qa_turn(
            session_id="test-session",
            feature="lecture-qa",
            question="What is AI?",
            answer="AI stands for Artificial Intelligence.",
            confidence="high",
            citations=[{"text": "source"}],
            retrieved_chunk_ids=["chunk1"],
            latency_ms=100,
            verifier_supported=True,
            outcome_reason="success",
        )

    @pytest.mark.asyncio
    async def test_track_llm_call_noop(
        self, noop_observer: NoopWeaveObserverService
    ) -> None:
        """track_llm_call should do nothing and not raise."""
        await noop_observer.track_llm_call(
            provider="azure-openai",
            model="gpt-4o",
            prompt="Test prompt",
            response="Test response",
            latency_ms=150,
            tokens_prompt=10,
            tokens_completion=20,
        )

    @pytest.mark.asyncio
    async def test_track_ocr_with_image_noop(
        self, noop_observer: NoopWeaveObserverService
    ) -> None:
        """track_ocr_with_image should do nothing and not raise."""
        await noop_observer.track_ocr_with_image(
            session_id="test-session",
            timestamp_ms=12345,
            source="azure-vision",
            ocr_text="Extracted text",
            ocr_confidence=0.95,
            quality="high",
            change_score=0.8,
            image_bytes=b"fake_image",
        )

    @pytest.mark.asyncio
    async def test_track_slide_transition_noop(
        self, noop_observer: NoopWeaveObserverService
    ) -> None:
        """track_slide_transition should do nothing and not raise."""
        await noop_observer.track_slide_transition(
            session_id="test-session",
            timestamp_ms=12345,
            slide_number=1,
            ocr_text="Slide text",
            image_bytes=b"fake_slide",
        )

    @pytest.mark.asyncio
    async def test_track_speech_event_noop(
        self, noop_observer: NoopWeaveObserverService
    ) -> None:
        """track_speech_event should do nothing and not raise."""
        await noop_observer.track_speech_event(
            session_id="test-session",
            start_ms=0,
            end_ms=5000,
            text="Hello world",
            original_text="herro warudo",
            confidence=0.9,
            is_final=True,
            speaker="speaker1",
        )

    @pytest.mark.asyncio
    async def test_with_session_context_noop(
        self, noop_observer: NoopWeaveObserverService
    ) -> None:
        """with_session_context should yield without side effects."""
        async with noop_observer.with_session_context("test-session"):
            # Context should be entered and exited without errors
            pass


class TestWandBWeaveObserverService:
    """Tests for WandBWeaveObserverService."""

    @pytest.fixture
    def weave_settings(self) -> WeaveSettings:
        """Create test Weave settings."""
        return WeaveSettings(
            enabled=True,
            project="test-project",
            mode="local",
            capture_prompts=True,
            capture_responses=True,
            capture_images=True,
            max_image_size_bytes=10_000_000,
            queue_maxsize=10,
            worker_count=1,
            timeout_ms=5000,
        )

    @pytest.fixture
    def wandb_observer(
        self, weave_settings: WeaveSettings
    ) -> WandBWeaveObserverService:
        """Create WandB observer instance."""
        return WandBWeaveObserverService(weave_settings)

    @pytest.mark.asyncio
    async def test_observer_initialization(
        self, wandb_observer: WandBWeaveObserverService
    ) -> None:
        """Observer should initialize with dispatcher."""
        assert wandb_observer._dispatcher_value is not None
        assert wandb_observer._settings is not None

    @pytest.mark.asyncio
    async def test_track_qa_turn_queue_full(
        self, wandb_observer: WandBWeaveObserverService
    ) -> None:
        """track_qa_turn should handle queue full gracefully."""
        # Fill the queue with blocking tasks
        dispatcher = wandb_observer._dispatcher_value

        async def blocking_task():
            await asyncio.sleep(10)

        # Fill queue beyond capacity
        for _ in range(20):  # More than queue_maxsize=10
            try:
                await dispatcher.dispatch(blocking_task)
            except Exception:
                break

        # Should not raise when queue is full
        await wandb_observer.track_qa_turn(
            session_id="test-session",
            feature="lecture-qa",
            question="Question?",
            answer="Answer.",
            confidence="high",
            citations=[],
            retrieved_chunk_ids=[],
            latency_ms=100,
            verifier_supported=True,
            outcome_reason="test",
        )

    @pytest.mark.asyncio
    async def test_track_llm_call_with_redaction(
        self, weave_settings: WeaveSettings
    ) -> None:
        """track_llm_call should redact when settings disable capture."""
        # Settings with prompts disabled - use model_copy
        settings_no_prompt = weave_settings.model_copy(
            update={"capture_prompts": False}
        )
        observer = WandBWeaveObserverService(settings_no_prompt)

        # Should not raise
        await observer.track_llm_call(
            provider="azure-openai",
            model="gpt-4o",
            prompt="Sensitive prompt",
            response="Response",
            latency_ms=100,
        )

    @pytest.mark.asyncio
    async def test_track_ocr_with_image_disabled(
        self, weave_settings: WeaveSettings
    ) -> None:
        """track_ocr_with_image should skip image when disabled."""
        settings_no_image = weave_settings.model_copy(update={"capture_images": False})
        observer = WandBWeaveObserverService(settings_no_image)

        # Should not raise even with large image
        large_image = b"x" * 20_000_000  # Larger than max_image_size_bytes
        await observer.track_ocr_with_image(
            session_id="test-session",
            timestamp_ms=12345,
            source="azure-vision",
            ocr_text="Text",
            ocr_confidence=0.9,
            quality="high",
            change_score=0.8,
            image_bytes=large_image,
        )

    @pytest.mark.asyncio
    async def test_track_slide_transition_with_blob_path(
        self, wandb_observer: WandBWeaveObserverService
    ) -> None:
        """track_slide_transition should accept blob path instead of image."""
        await wandb_observer.track_slide_transition(
            session_id="test-session",
            timestamp_ms=12345,
            slide_number=1,
            ocr_text="Slide text",
            blob_path="azure-blob://container/slide.jpg",
        )

    @pytest.mark.asyncio
    async def test_track_speech_event_without_original(
        self, wandb_observer: WandBWeaveObserverService
    ) -> None:
        """track_speech_event should work without original_text."""
        await wandb_observer.track_speech_event(
            session_id="test-session",
            start_ms=0,
            end_ms=5000,
            text="Corrected text",
            original_text=None,
            confidence=0.9,
            is_final=True,
            speaker="speaker1",
        )

    @pytest.mark.asyncio
    async def test_with_session_context(
        self, wandb_observer: WandBWeaveObserverService
    ) -> None:
        """with_session_context should provide context manager."""
        async with wandb_observer.with_session_context("test-session"):
            # Context should be available
            pass

    @pytest.mark.asyncio
    async def test_multiple_concurrent_calls(
        self, wandb_observer: WandBWeaveObserverService
    ) -> None:
        """Multiple concurrent calls should be handled."""
        tasks = [
            wandb_observer.track_qa_turn(
                session_id=f"session-{i}",
                feature="lecture-qa",
                question=f"Question {i}?",
                answer=f"Answer {i}.",
                confidence="high",
                citations=[],
                retrieved_chunk_ids=[],
                latency_ms=100,
                verifier_supported=True,
                outcome_reason="test",
            )
            for i in range(5)
        ]
        await asyncio.gather(*tasks)

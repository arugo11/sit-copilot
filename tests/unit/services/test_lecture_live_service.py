"""Unit tests for lecture live service."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.speech_review_history import SpeechReviewHistory
from app.models.visual_event import VisualEvent
from app.schemas.lecture import (
    MAX_VISUAL_IMAGE_BYTES,
    LectureSessionStartRequest,
    LectureVisualSource,
    SpeechChunkIngestRequest,
    VisualEventIngestRequest,
)
from app.services.lecture_live_service import (
    LectureSpeechEventNotFoundError,
    LectureSessionInactiveError,
    LectureSessionNotFoundError,
    SqlAlchemyLectureLiveService,
)
from app.services.vision_ocr_service import VisionOCRResult, VisionOCRServiceError
from app.services.vision_ocr_service import AzureVisionOCRService
from app.services.asr_hallucination_judge_service import (
    NoopJapaneseASRHallucinationJudgeService,
)


class FakeVisionOCRService:
    """Fake OCR service for deterministic success tests."""

    async def extract_text(
        self,
        image_bytes: bytes,
        source: LectureVisualSource,
    ) -> VisionOCRResult:
        del image_bytes, source
        return VisionOCRResult(
            text="外れ値, 残差確認",
            confidence=0.82,
        )


class FailingVisionOCRService:
    """OCR service that raises to test fallback behavior."""

    async def extract_text(
        self,
        image_bytes: bytes,
        source: LectureVisualSource,
    ) -> VisionOCRResult:
        del image_bytes, source
        raise VisionOCRServiceError("simulated ocr failure")


class FakeJapaneseCorrectionService:
    """Correction service that applies deterministic minimal correction."""

    async def correct_minimally(self, text: str) -> str:
        return text.replace("学習", "がくしゅう")


class IdentityJapaneseCorrectionService:
    """Correction service that keeps input unchanged."""

    async def correct_minimally(self, text: str) -> str:
        return text


class FailingJapaneseCorrectionService:
    """Correction service that always fails for retry-path tests."""

    async def correct_minimally(self, text: str) -> str:
        raise RuntimeError("simulated correction failure")


class FakeApproveAllJudgeService:
    """Judge that auto-approves all corrections (not Noop, so constructor won't replace)."""

    async def judge(
        self, *, original_text: str, candidate_text: str
    ) -> "HallucinationJudgeResult":
        from app.services.asr_hallucination_judge_service import HallucinationJudgeResult

        changed = candidate_text.strip() != original_text.strip()
        return HallucinationJudgeResult(
            should_apply=changed, confidence=1.0, reason="fake_approve_all"
        )


@pytest.mark.asyncio
async def test_service_auto_uses_azure_vision_provider_when_configured(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Service should switch from noop to Azure Vision provider when configured."""
    monkeypatch.setattr(settings, "azure_vision_enabled", True)
    monkeypatch.setattr(settings, "azure_vision_key", "dummy-key")
    monkeypatch.setattr(
        settings,
        "azure_vision_endpoint",
        "https://japaneast.api.cognitive.microsoft.com",
    )

    service = SqlAlchemyLectureLiveService(db_session, user_id="demo_user")

    assert isinstance(service._vision_ocr_service, AzureVisionOCRService)


@pytest.mark.asyncio
async def test_start_session_persists_active_lecture_session(
    db_session: AsyncSession,
) -> None:
    """start_session should create an active lecture session row."""
    service = SqlAlchemyLectureLiveService(db_session, user_id="demo_user")
    request = LectureSessionStartRequest(
        course_name="統計学基礎",
        course_id=None,
        lang_mode="ja",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
    )

    response = await service.start_session(request)

    assert response.status == "active"
    assert response.session_id.startswith("lec_")

    result = await db_session.execute(
        select(LectureSession).where(LectureSession.id == response.session_id)
    )
    session = result.scalar_one_or_none()
    assert session is not None
    assert session.course_name == request.course_name
    assert session.status == "active"
    assert session.consent_acknowledged is True


@pytest.mark.asyncio
async def test_ingest_speech_chunk_persists_event_for_active_session(
    db_session: AsyncSession,
) -> None:
    """ingest_speech_chunk should persist a speech event."""
    service = SqlAlchemyLectureLiveService(
        db_session,
        user_id="demo_user",
        correction_service=FakeJapaneseCorrectionService(),
    )
    start_response = await service.start_session(
        LectureSessionStartRequest(
            course_name="統計学基礎",
            course_id=None,
            lang_mode="ja",
            camera_enabled=True,
            slide_roi=[100, 80, 900, 520],
            board_roi=[80, 560, 920, 980],
            consent_acknowledged=True,
        )
    )
    request = SpeechChunkIngestRequest(
        session_id=start_response.session_id,
        start_ms=15000,
        end_ms=20000,
        text="機械学習の外れ値は散布図で確認します。",
        confidence=0.93,
        is_final=True,
        speaker="teacher",
    )

    response = await service.ingest_speech_chunk(request)

    assert response.accepted is True
    assert response.session_id == start_response.session_id
    assert response.event_id != ""

    result = await db_session.execute(
        select(SpeechEvent).where(SpeechEvent.id == response.event_id)
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.session_id == start_response.session_id
    assert event.text == request.text
    assert event.original_text == request.text
    assert event.speaker == request.speaker


@pytest.mark.asyncio
async def test_audit_and_apply_speech_chunk_updates_display_text(
    db_session: AsyncSession,
) -> None:
    """audit_and_apply_speech_chunk should replace displayed subtitle text."""
    service = SqlAlchemyLectureLiveService(
        db_session,
        user_id="demo_user",
        correction_service=FakeJapaneseCorrectionService(),
        judge_service=FakeApproveAllJudgeService(),
    )
    start_response = await service.start_session(
        LectureSessionStartRequest(
            course_name="統計学基礎",
            course_id=None,
            lang_mode="ja",
            camera_enabled=True,
            slide_roi=[100, 80, 900, 520],
            board_roi=[80, 560, 920, 980],
            consent_acknowledged=True,
        )
    )
    ingest_response = await service.ingest_speech_chunk(
        SpeechChunkIngestRequest(
            session_id=start_response.session_id,
            start_ms=15000,
            end_ms=20000,
            text="機械学習の外れ値は散布図で確認します。",
            confidence=0.93,
            is_final=True,
            speaker="teacher",
        )
    )

    audited = await service.audit_and_apply_speech_chunk(
        session_id=start_response.session_id,
        event_id=ingest_response.event_id,
    )

    assert audited.updated is True
    assert audited.event_id == ingest_response.event_id
    assert audited.corrected_text == "機械がくしゅうの外れ値は散布図で確認します。"

    result = await db_session.execute(
        select(SpeechEvent).where(SpeechEvent.id == ingest_response.event_id)
    )
    event = result.scalar_one()
    assert event.original_text == "機械学習の外れ値は散布図で確認します。"
    assert event.text == "機械がくしゅうの外れ値は散布図で確認します。"


@pytest.mark.asyncio
async def test_audit_and_apply_speech_chunk_raises_not_found_for_unknown_event(
    db_session: AsyncSession,
) -> None:
    """audit_and_apply_speech_chunk should raise not-found for unknown event."""
    service = SqlAlchemyLectureLiveService(db_session, user_id="demo_user")
    start_response = await service.start_session(
        LectureSessionStartRequest(
            course_name="統計学基礎",
            course_id=None,
            lang_mode="ja",
            camera_enabled=True,
            slide_roi=[100, 80, 900, 520],
            board_roi=[80, 560, 920, 980],
            consent_acknowledged=True,
        )
    )

    with pytest.raises(LectureSpeechEventNotFoundError):
        await service.audit_and_apply_speech_chunk(
            session_id=start_response.session_id,
            event_id="missing-event-id",
        )


@pytest.mark.asyncio
async def test_audit_and_apply_speech_chunk_marks_reviewed_when_text_is_unchanged(
    db_session: AsyncSession,
) -> None:
    """Unchanged correction result should still be treated as reviewed."""
    service = SqlAlchemyLectureLiveService(
        db_session,
        user_id="demo_user",
        correction_service=IdentityJapaneseCorrectionService(),
    )
    start_response = await service.start_session(
        LectureSessionStartRequest(
            course_name="統計学基礎",
            course_id=None,
            lang_mode="ja",
            camera_enabled=True,
            slide_roi=[100, 80, 900, 520],
            board_roi=[80, 560, 920, 980],
            consent_acknowledged=True,
        )
    )
    ingest_response = await service.ingest_speech_chunk(
        SpeechChunkIngestRequest(
            session_id=start_response.session_id,
            start_ms=1000,
            end_ms=2000,
            text="外れ値がある場合は散布図で確認します。",
            confidence=0.9,
            is_final=True,
            speaker="teacher",
        )
    )

    audited = await service.audit_and_apply_speech_chunk(
        session_id=start_response.session_id,
        event_id=ingest_response.event_id,
    )

    assert audited.review_status == "reviewed"
    assert audited.reviewed is True
    assert audited.was_corrected is False
    assert audited.updated is False


@pytest.mark.asyncio
async def test_audit_and_apply_speech_chunk_sets_review_failed_after_retry_exhaustion(
    db_session: AsyncSession,
) -> None:
    """Failure path should return review_failed and persist attempt history."""
    service = SqlAlchemyLectureLiveService(
        db_session,
        user_id="demo_user",
        correction_service=FailingJapaneseCorrectionService(),
    )
    start_response = await service.start_session(
        LectureSessionStartRequest(
            course_name="統計学基礎",
            course_id=None,
            lang_mode="ja",
            camera_enabled=True,
            slide_roi=[100, 80, 900, 520],
            board_roi=[80, 560, 920, 980],
            consent_acknowledged=True,
        )
    )
    ingest_response = await service.ingest_speech_chunk(
        SpeechChunkIngestRequest(
            session_id=start_response.session_id,
            start_ms=1000,
            end_ms=2000,
            text="外れ値がある場合は散布図で確認します。",
            confidence=0.9,
            is_final=True,
            speaker="teacher",
        )
    )

    audited = await service.audit_and_apply_speech_chunk(
        session_id=start_response.session_id,
        event_id=ingest_response.event_id,
    )

    assert audited.review_status == "review_failed"
    assert audited.reviewed is False
    assert audited.was_corrected is False
    assert audited.corrected_text == "外れ値がある場合は散布図で確認します。"

    history_result = await db_session.execute(
        select(SpeechReviewHistory).where(
            SpeechReviewHistory.speech_event_id == ingest_response.event_id
        )
    )
    histories = list(history_result.scalars().all())
    assert len(histories) >= 1


@pytest.mark.asyncio
async def test_ingest_speech_chunk_raises_not_found_for_unknown_session(
    db_session: AsyncSession,
) -> None:
    """ingest_speech_chunk should raise not-found for unknown session."""
    service = SqlAlchemyLectureLiveService(db_session, user_id="demo_user")
    request = SpeechChunkIngestRequest(
        session_id="lec_20260220_unknown",
        start_ms=15000,
        end_ms=20000,
        text="外れ値がある場合は散布図で確認します。",
        confidence=0.93,
        is_final=True,
        speaker="teacher",
    )

    with pytest.raises(LectureSessionNotFoundError):
        await service.ingest_speech_chunk(request)


@pytest.mark.asyncio
async def test_ingest_speech_chunk_raises_inactive_for_non_active_session(
    db_session: AsyncSession,
) -> None:
    """ingest_speech_chunk should reject non-active sessions."""
    session = LectureSession(
        id="lec_20260220_inactive",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="finalized",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
    )
    db_session.add(session)
    await db_session.flush()

    service = SqlAlchemyLectureLiveService(db_session, user_id="demo_user")
    request = SpeechChunkIngestRequest(
        session_id=session.id,
        start_ms=15000,
        end_ms=20000,
        text="外れ値がある場合は散布図で確認します。",
        confidence=0.93,
        is_final=True,
        speaker="teacher",
    )

    with pytest.raises(LectureSessionInactiveError):
        await service.ingest_speech_chunk(request)


@pytest.mark.asyncio
async def test_ingest_speech_chunk_accepts_legacy_live_status_session(
    db_session: AsyncSession,
) -> None:
    """ingest_speech_chunk should accept legacy sessions with status=live."""
    session = LectureSession(
        id="lec_20260220_live_legacy",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="live",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
    )
    db_session.add(session)
    await db_session.flush()

    service = SqlAlchemyLectureLiveService(db_session, user_id="demo_user")
    request = SpeechChunkIngestRequest(
        session_id=session.id,
        start_ms=15000,
        end_ms=20000,
        text="外れ値がある場合は散布図で確認します。",
        confidence=0.93,
        is_final=True,
        speaker="teacher",
    )

    response = await service.ingest_speech_chunk(request)

    assert response.accepted is True
    assert response.session_id == session.id
    assert response.event_id != ""


@pytest.mark.asyncio
async def test_ingest_speech_chunk_raises_not_found_for_other_user_session(
    db_session: AsyncSession,
) -> None:
    """ingest_speech_chunk should reject session owned by another user."""
    session = LectureSession(
        id="lec_20260220_owner_a",
        user_id="owner_a",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="active",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
    )
    db_session.add(session)
    await db_session.flush()

    service = SqlAlchemyLectureLiveService(db_session, user_id="owner_b")
    request = SpeechChunkIngestRequest(
        session_id=session.id,
        start_ms=15000,
        end_ms=20000,
        text="外れ値がある場合は散布図で確認します。",
        confidence=0.93,
        is_final=True,
        speaker="teacher",
    )

    with pytest.raises(LectureSessionNotFoundError):
        await service.ingest_speech_chunk(request)


@pytest.mark.asyncio
async def test_ingest_visual_event_persists_event_for_active_session(
    db_session: AsyncSession,
) -> None:
    """ingest_visual_event should persist OCR metadata for active sessions."""
    service = SqlAlchemyLectureLiveService(
        db_session,
        user_id="demo_user",
        vision_ocr_service=FakeVisionOCRService(),
    )
    start_response = await service.start_session(
        LectureSessionStartRequest(
            course_name="統計学基礎",
            course_id=None,
            lang_mode="ja",
            camera_enabled=True,
            slide_roi=[100, 80, 900, 520],
            board_roi=[80, 560, 920, 980],
            consent_acknowledged=True,
        )
    )
    request = VisualEventIngestRequest(
        session_id=start_response.session_id,
        timestamp_ms=18000,
        source="slide",
        change_score=0.38,
        image_content_type="image/jpeg",
        image_size=12,
        upload_size_limit=MAX_VISUAL_IMAGE_BYTES,
        image_has_jpeg_magic=True,
    )

    response = await service.ingest_visual_event(
        request=request,
        image_bytes=b"jpeg-bytes",
    )

    assert response.event_id != ""
    assert response.ocr_text == "外れ値, 残差確認"
    assert response.ocr_confidence == 0.82
    assert response.quality == "good"

    result = await db_session.execute(
        select(VisualEvent).where(VisualEvent.id == response.event_id)
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.session_id == start_response.session_id
    assert event.source == "slide"
    assert event.change_score == 0.38
    assert event.quality == "good"


@pytest.mark.asyncio
async def test_ingest_visual_event_persists_bad_quality_when_ocr_fails(
    db_session: AsyncSession,
) -> None:
    """ingest_visual_event should persist fallback record on OCR failure."""
    service = SqlAlchemyLectureLiveService(
        db_session,
        user_id="demo_user",
        vision_ocr_service=FailingVisionOCRService(),
    )
    start_response = await service.start_session(
        LectureSessionStartRequest(
            course_name="統計学基礎",
            course_id=None,
            lang_mode="ja",
            camera_enabled=True,
            slide_roi=[100, 80, 900, 520],
            board_roi=[80, 560, 920, 980],
            consent_acknowledged=True,
        )
    )
    request = VisualEventIngestRequest(
        session_id=start_response.session_id,
        timestamp_ms=22000,
        source="board",
        change_score=0.12,
        image_content_type="image/jpeg",
        image_size=10,
        upload_size_limit=MAX_VISUAL_IMAGE_BYTES,
        image_has_jpeg_magic=True,
    )

    response = await service.ingest_visual_event(
        request=request,
        image_bytes=b"jpeg-bytes",
    )

    assert response.ocr_text == ""
    assert response.ocr_confidence == 0.0
    assert response.quality == "bad"

    result = await db_session.execute(
        select(VisualEvent).where(VisualEvent.id == response.event_id)
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.quality == "bad"


@pytest.mark.asyncio
async def test_ingest_visual_event_raises_not_found_for_unknown_session(
    db_session: AsyncSession,
) -> None:
    """ingest_visual_event should raise not-found for unknown session."""
    service = SqlAlchemyLectureLiveService(
        db_session,
        user_id="demo_user",
        vision_ocr_service=FakeVisionOCRService(),
    )
    request = VisualEventIngestRequest(
        session_id="lec_20260220_unknown",
        timestamp_ms=18000,
        source="slide",
        change_score=0.38,
        image_content_type="image/jpeg",
        image_size=10,
        upload_size_limit=MAX_VISUAL_IMAGE_BYTES,
        image_has_jpeg_magic=True,
    )

    with pytest.raises(LectureSessionNotFoundError):
        await service.ingest_visual_event(request=request, image_bytes=b"jpeg-bytes")


@pytest.mark.asyncio
async def test_ingest_visual_event_raises_inactive_for_non_active_session(
    db_session: AsyncSession,
) -> None:
    """ingest_visual_event should reject non-active sessions."""
    session = LectureSession(
        id="lec_20260220_inactive_visual",
        user_id="demo_user",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="finalized",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
    )
    db_session.add(session)
    await db_session.flush()

    service = SqlAlchemyLectureLiveService(
        db_session,
        user_id="demo_user",
        vision_ocr_service=FakeVisionOCRService(),
    )
    request = VisualEventIngestRequest(
        session_id=session.id,
        timestamp_ms=18000,
        source="slide",
        change_score=0.38,
        image_content_type="image/jpeg",
        image_size=10,
        upload_size_limit=MAX_VISUAL_IMAGE_BYTES,
        image_has_jpeg_magic=True,
    )

    with pytest.raises(LectureSessionInactiveError):
        await service.ingest_visual_event(request=request, image_bytes=b"jpeg-bytes")


@pytest.mark.asyncio
async def test_ingest_visual_event_raises_not_found_for_other_user_session(
    db_session: AsyncSession,
) -> None:
    """ingest_visual_event should reject session owned by another user."""
    session = LectureSession(
        id="lec_20260220_owner_visual_a",
        user_id="owner_a",
        course_id=None,
        course_name="統計学基礎",
        lang_mode="ja",
        status="active",
        camera_enabled=True,
        slide_roi=[100, 80, 900, 520],
        board_roi=[80, 560, 920, 980],
        consent_acknowledged=True,
    )
    db_session.add(session)
    await db_session.flush()

    service = SqlAlchemyLectureLiveService(
        db_session,
        user_id="owner_b",
        vision_ocr_service=FakeVisionOCRService(),
    )
    request = VisualEventIngestRequest(
        session_id=session.id,
        timestamp_ms=18000,
        source="slide",
        change_score=0.38,
        image_content_type="image/jpeg",
        image_size=12,
        upload_size_limit=MAX_VISUAL_IMAGE_BYTES,
        image_has_jpeg_magic=True,
    )

    with pytest.raises(LectureSessionNotFoundError):
        await service.ingest_visual_event(request=request, image_bytes=b"jpeg-bytes")

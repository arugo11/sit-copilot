"""Unit tests for lecture live service."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.visual_event import VisualEvent
from app.schemas.lecture import (
    MAX_VISUAL_IMAGE_BYTES,
    LectureSessionStartRequest,
    LectureVisualSource,
    SpeechChunkIngestRequest,
    VisualEventIngestRequest,
)
from app.services.lecture_live_service import (
    LectureSessionInactiveError,
    LectureSessionNotFoundError,
    SqlAlchemyLectureLiveService,
)
from app.services.vision_ocr_service import VisionOCRResult, VisionOCRServiceError


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
    request = SpeechChunkIngestRequest(
        session_id=start_response.session_id,
        start_ms=15000,
        end_ms=20000,
        text="外れ値がある場合は散布図で確認します。",
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
    assert event.speaker == request.speaker


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

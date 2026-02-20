"""Integration tests for lecture live API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth import LECTURE_TOKEN_HEADER, USER_ID_HEADER
from app.core.config import settings
from app.models.lecture_chunk import LectureChunk
from app.models.lecture_session import LectureSession
from app.models.speech_event import SpeechEvent
from app.models.summary_window import SummaryWindow
from app.models.visual_event import VisualEvent

AUTH_HEADERS = {
    LECTURE_TOKEN_HEADER: settings.lecture_api_token,
    USER_ID_HEADER: "demo_user",
}
OWNER_A_HEADERS = {
    LECTURE_TOKEN_HEADER: settings.lecture_api_token,
    USER_ID_HEADER: "owner_a",
}
OWNER_B_HEADERS = {
    LECTURE_TOKEN_HEADER: settings.lecture_api_token,
    USER_ID_HEADER: "owner_b",
}
JPEG_BYTES = b"\xff\xd8\xff\xe0fake-jpeg\xff\xd9"


@pytest.mark.asyncio
async def test_post_lecture_session_start_returns_200_and_persists(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """POST /lecture/session/start should create active session."""
    payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }

    response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=payload,
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "active"
    assert body["session_id"].startswith("lec_")

    async with session_factory() as session:
        result = await session.execute(
            select(LectureSession).where(LectureSession.id == body["session_id"])
        )
        lecture_session = result.scalar_one_or_none()
    assert lecture_session is not None
    assert lecture_session.course_name == payload["course_name"]


@pytest.mark.asyncio
async def test_post_lecture_session_start_with_false_consent_returns_400(
    async_client: AsyncClient,
) -> None:
    """Session start should reject requests without consent acknowledgement."""
    payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": False,
    }

    response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=payload,
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_post_lecture_session_start_without_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Session start should reject requests without lecture token."""
    payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }

    response = await async_client.post("/api/v4/lecture/session/start", json=payload)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_lecture_speech_chunk_returns_200_and_persists(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Speech chunk endpoint should persist finalized subtitle event."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]
    chunk_payload = {
        "session_id": session_id,
        "start_ms": 15000,
        "end_ms": 20000,
        "text": "外れ値がある場合は散布図で確認します。",
        "confidence": 0.93,
        "is_final": True,
        "speaker": "teacher",
    }

    response = await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json=chunk_payload,
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["accepted"] is True
    assert body["event_id"] != ""

    async with session_factory() as session:
        result = await session.execute(
            select(SpeechEvent).where(SpeechEvent.id == body["event_id"])
        )
        speech_event = result.scalar_one_or_none()
    assert speech_event is not None
    assert speech_event.session_id == session_id
    assert speech_event.text == chunk_payload["text"]


@pytest.mark.asyncio
async def test_post_lecture_speech_chunk_with_unknown_session_returns_404(
    async_client: AsyncClient,
) -> None:
    """Speech chunk endpoint should return 404 for unknown session ID."""
    chunk_payload = {
        "session_id": "lec_20260220_unknown",
        "start_ms": 15000,
        "end_ms": 20000,
        "text": "外れ値がある場合は散布図で確認します。",
        "confidence": 0.93,
        "is_final": True,
        "speaker": "teacher",
    }

    response = await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json=chunk_payload,
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_post_lecture_speech_chunk_with_invalid_time_range_returns_400(
    async_client: AsyncClient,
) -> None:
    """Speech chunk endpoint should reject invalid timing range."""
    chunk_payload = {
        "session_id": "lec_20260220_unknown",
        "start_ms": 20000,
        "end_ms": 15000,
        "text": "外れ値がある場合は散布図で確認します。",
        "confidence": 0.93,
        "is_final": True,
        "speaker": "teacher",
    }

    response = await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json=chunk_payload,
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_post_lecture_speech_chunk_with_inactive_session_returns_409(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Speech chunk endpoint should return 409 for non-active sessions."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    async with session_factory() as session:
        result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        lecture_session = result.scalar_one()
        lecture_session.status = "finalized"
        await session.commit()

    chunk_payload = {
        "session_id": session_id,
        "start_ms": 15000,
        "end_ms": 20000,
        "text": "外れ値がある場合は散布図で確認します。",
        "confidence": 0.93,
        "is_final": True,
        "speaker": "teacher",
    }
    response = await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json=chunk_payload,
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 409
    assert body["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_post_lecture_visual_event_returns_200_and_persists(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Visual event endpoint should persist OCR metadata."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]
    response = await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": session_id,
            "timestamp_ms": "18000",
            "source": "slide",
            "change_score": "0.42",
        },
        files={"image": ("frame.jpg", JPEG_BYTES, "image/jpeg")},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["event_id"] != ""
    assert body["quality"] == "bad"
    assert body["ocr_confidence"] == 0.0

    async with session_factory() as session:
        result = await session.execute(
            select(VisualEvent).where(VisualEvent.id == body["event_id"])
        )
        visual_event = result.scalar_one_or_none()
    assert visual_event is not None
    assert visual_event.session_id == session_id
    assert visual_event.source == "slide"
    assert visual_event.timestamp_ms == 18000


@pytest.mark.asyncio
async def test_post_lecture_visual_event_with_unknown_session_returns_404(
    async_client: AsyncClient,
) -> None:
    """Visual event endpoint should return 404 for unknown session."""
    response = await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": "lec_20260220_unknown",
            "timestamp_ms": "18000",
            "source": "slide",
            "change_score": "0.42",
        },
        files={"image": ("frame.jpg", JPEG_BYTES, "image/jpeg")},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_post_lecture_visual_event_with_inactive_session_returns_409(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Visual event endpoint should return 409 for non-active sessions."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    async with session_factory() as session:
        result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        lecture_session = result.scalar_one()
        lecture_session.status = "finalized"
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": session_id,
            "timestamp_ms": "18000",
            "source": "slide",
            "change_score": "0.42",
        },
        files={"image": ("frame.jpg", JPEG_BYTES, "image/jpeg")},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 409
    assert body["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_post_lecture_visual_event_without_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Visual event endpoint should reject requests without lecture token."""
    response = await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": "lec_20260220_unknown",
            "timestamp_ms": "18000",
            "source": "slide",
            "change_score": "0.42",
        },
        files={"image": ("frame.jpg", JPEG_BYTES, "image/jpeg")},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_lecture_visual_event_with_invalid_content_type_returns_400(
    async_client: AsyncClient,
) -> None:
    """Visual event endpoint should reject non-JPEG image content types."""
    response = await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": "lec_20260220_unknown",
            "timestamp_ms": "18000",
            "source": "slide",
            "change_score": "0.42",
        },
        files={"image": ("frame.png", b"fake-png", "image/png")},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_post_lecture_visual_event_with_invalid_jpeg_signature_returns_400(
    async_client: AsyncClient,
) -> None:
    """Visual event endpoint should reject invalid JPEG payload signature."""
    response = await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": "lec_20260220_unknown",
            "timestamp_ms": "18000",
            "source": "slide",
            "change_score": "0.42",
        },
        files={"image": ("frame.jpg", b"not-a-jpeg", "image/jpeg")},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_post_lecture_visual_event_with_oversized_image_returns_400(
    async_client: AsyncClient,
) -> None:
    """Visual event endpoint should reject uploads over configured max size."""
    oversized_bytes = b"\xff\xd8\xff" + (b"a" * settings.lecture_visual_max_image_bytes)
    response = await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": "lec_20260220_unknown",
            "timestamp_ms": "18000",
            "source": "slide",
            "change_score": "0.42",
        },
        files={"image": ("frame.jpg", oversized_bytes, "image/jpeg")},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_post_lecture_visual_event_for_other_user_session_returns_404(
    async_client: AsyncClient,
) -> None:
    """Visual event endpoint should reject sessions owned by another user."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=OWNER_A_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    response = await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": session_id,
            "timestamp_ms": "18000",
            "source": "slide",
            "change_score": "0.42",
        },
        files={"image": ("frame.jpg", JPEG_BYTES, "image/jpeg")},
        headers=OWNER_B_HEADERS,
    )
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_returns_200_and_persists_window(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Summary latest endpoint should return a generated summary window."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 15000,
            "end_ms": 22000,
            "text": "外れ値の確認手順を説明します。",
            "confidence": 0.93,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )
    await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": session_id,
            "timestamp_ms": "21000",
            "source": "board",
            "change_score": "0.42",
        },
        files={"image": ("frame.jpg", JPEG_BYTES, "image/jpeg")},
        headers=AUTH_HEADERS,
    )

    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["window_end_ms"] >= 30000
    assert "summary" in body
    assert "key_terms" in body
    assert "evidence" in body

    async with session_factory() as session:
        result = await session.execute(
            select(SummaryWindow).where(SummaryWindow.session_id == session_id)
        )
        summary_window = result.scalar_one_or_none()
    assert summary_window is not None


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_with_unknown_session_returns_404(
    async_client: AsyncClient,
) -> None:
    """Summary latest endpoint should return 404 for unknown session."""
    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": "lec_missing"},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_without_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Summary latest endpoint should reject requests without lecture token."""
    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": "lec_missing"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_for_other_user_session_returns_404(
    async_client: AsyncClient,
) -> None:
    """Summary latest endpoint should enforce session ownership."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=OWNER_A_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=OWNER_B_HEADERS,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_lecture_session_finalize_returns_200_and_stats(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Finalize endpoint should finalize session and return artifact stats."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 15000,
            "end_ms": 22000,
            "text": "外れ値の確認手順を説明します。",
            "confidence": 0.93,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )

    response = await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={
            "session_id": session_id,
            "build_qa_index": False,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["status"] == "finalized"
    assert body["stats"]["speech_events"] >= 1
    assert body["stats"]["summary_windows"] >= 1
    assert body["stats"]["lecture_chunks"] >= 1

    async with session_factory() as session:
        session_result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        finalized_session = session_result.scalar_one()
        chunk_result = await session.execute(
            select(LectureChunk).where(LectureChunk.session_id == session_id)
        )
        chunks = chunk_result.scalars().all()

    assert finalized_session.status == "finalized"
    assert len(chunks) == body["stats"]["lecture_chunks"]


@pytest.mark.asyncio
async def test_post_lecture_session_finalize_is_idempotent(
    async_client: AsyncClient,
) -> None:
    """Finalize endpoint should be safe to call repeatedly."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 15000,
            "end_ms": 22000,
            "text": "再実行テスト用イベント。",
            "confidence": 0.93,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )

    first = await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={
            "session_id": session_id,
            "build_qa_index": False,
        },
        headers=AUTH_HEADERS,
    )
    second = await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={
            "session_id": session_id,
            "build_qa_index": False,
        },
        headers=AUTH_HEADERS,
    )

    first_body = first.json()
    second_body = second.json()

    assert first.status_code == 200
    assert second.status_code == 200
    assert second_body["status"] == "finalized"
    assert (
        second_body["stats"]["lecture_chunks"] == first_body["stats"]["lecture_chunks"]
    )


@pytest.mark.asyncio
async def test_post_lecture_session_finalize_without_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Finalize endpoint should reject requests without lecture token."""
    response = await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={"session_id": "lec_missing", "build_qa_index": False},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_lecture_session_finalize_with_unknown_session_returns_404(
    async_client: AsyncClient,
) -> None:
    """Finalize endpoint should return 404 for unknown session."""
    response = await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={"session_id": "lec_missing", "build_qa_index": False},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_lecture_session_finalize_for_other_user_session_returns_404(
    async_client: AsyncClient,
) -> None:
    """Finalize endpoint should enforce session ownership."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=OWNER_A_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    response = await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={"session_id": session_id, "build_qa_index": False},
        headers=OWNER_B_HEADERS,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_lecture_session_finalize_with_invalid_status_returns_409(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Finalize endpoint should return 409 when session state is invalid."""
    start_payload = {
        "course_name": "統計学基礎",
        "course_id": None,
        "lang_mode": "ja",
        "camera_enabled": True,
        "slide_roi": [100, 80, 900, 520],
        "board_roi": [80, 560, 920, 980],
        "consent_acknowledged": True,
    }
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json=start_payload,
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    async with session_factory() as session:
        result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        lecture_session = result.scalar_one()
        lecture_session.status = "error"
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={"session_id": session_id, "build_qa_index": False},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 409

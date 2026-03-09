"""Integration tests for lecture live API endpoints."""

import json
from unittest.mock import Mock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth import LECTURE_TOKEN_HEADER, USER_ID_HEADER
from app.core.config import settings
from app.main import app
from app.models.lecture_chunk import LectureChunk
from app.models.lecture_session import LectureSession
from app.models.qa_turn import QATurn
from app.models.speech_event import SpeechEvent
from app.models.speech_review_history import SpeechReviewHistory
from app.models.summary_window import SummaryWindow
from app.models.visual_event import VisualEvent

AUTH_HEADERS = {
    LECTURE_TOKEN_HEADER: settings.lecture_api_token,
    USER_ID_HEADER: "demo_user",
}
LEGACY_DEMO_HEADERS = {
    LECTURE_TOKEN_HEADER: settings.lecture_api_token,
    USER_ID_HEADER: "demo-user",
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


def _parse_sse_events(raw_payload: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for raw_block in raw_payload.split("\n\n"):
        if not raw_block or raw_block.startswith(":"):
            continue

        data_lines = [
            line[5:].strip()
            for line in raw_block.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue

        parsed = json.loads("\n".join(data_lines))
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


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
    assert speech_event.original_text == chunk_payload["text"]


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
async def test_get_lecture_events_stream_returns_sse_events(
    async_client: AsyncClient,
) -> None:
    """SSE endpoint should stream transcript/source/assist events for a session."""
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
            "start_ms": 0,
            "end_ms": 4000,
            "text": "講義導入です。",
            "confidence": 0.91,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )
    await async_client.post(
        "/api/v4/lecture/visual/event",
        data={
            "session_id": session_id,
            "timestamp_ms": "3000",
            "source": "slide",
            "change_score": "0.42",
        },
        files={"image": ("frame.jpg", JPEG_BYTES, "image/jpeg")},
        headers=AUTH_HEADERS,
    )
    await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=AUTH_HEADERS,
    )
    response = await async_client.get(
        "/api/v4/lecture/events/stream",
        params={"session_id": session_id, "once": "true"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_events(response.text)

    event_types = [event.get("type") for event in events]
    assert "session.status" in event_types
    assert "transcript.final" in event_types
    assert "source.frame" in event_types
    assert "source.ocr" in event_types

    transcript_events = [e for e in events if e.get("type") == "transcript.final"]
    assert transcript_events
    transcript_payload = transcript_events[0]["payload"]
    assert transcript_payload["sourceLangText"] == "講義導入です。"
    assert (
        transcript_payload.get("originalLangText")
        or transcript_payload["sourceLangText"]
    ) == "講義導入です。"


@pytest.mark.asyncio
async def test_get_lecture_events_stream_omits_assist_events_when_env_flags_off(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSE stream should not emit cached assist events when env flags are off."""
    monkeypatch.setattr(settings, "lecture_live_summary_enabled", False)
    monkeypatch.setattr(settings, "lecture_live_keyterms_enabled", False)

    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "統計学基礎",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 0,
            "end_ms": 4000,
            "text": "講義導入です。",
            "confidence": 0.91,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )

    async with session_factory() as session:
        session.add(
            SummaryWindow(
                session_id=session_id,
                start_ms=0,
                end_ms=30000,
                summary_text="送信されてはいけない要約です。",
                key_terms_json=[
                    {
                        "term": "外れ値",
                        "explanation": "送信されない",
                        "translation": "outlier",
                    }
                ],
                evidence_event_ids_json=[],
            )
        )
        await session.commit()

    response = await async_client.get(
        "/api/v4/lecture/events/stream",
        params={"session_id": session_id, "once": "true"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    event_types = [event.get("type") for event in events]
    assert "assist.summary" not in event_types
    assert "assist.term" not in event_types


@pytest.mark.asyncio
async def test_get_lecture_events_stream_without_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """SSE endpoint should reject unauthenticated requests."""
    response = await async_client.get(
        "/api/v4/lecture/events/stream",
        params={"session_id": "lec_missing"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_lecture_events_stream_for_other_user_session_returns_404(
    async_client: AsyncClient,
) -> None:
    """SSE endpoint should enforce session ownership before starting stream."""
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
        "/api/v4/lecture/events/stream",
        params={"session_id": session_id},
        headers=OWNER_B_HEADERS,
    )
    assert response.status_code == 404


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
        "/api/v4/settings/me",
        json={
            "settings": {
                "assistSummaryEnabled": True,
                "assistKeytermsEnabled": True,
            }
        },
        headers=AUTH_HEADERS,
    )

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
async def test_get_lecture_summary_latest_returns_off_when_summary_disabled(
    async_client: AsyncClient,
) -> None:
    """Summary latest endpoint should return off when assist summary is disabled."""
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
        "/api/v4/settings/me",
        json={
            "settings": {
                "assistSummaryEnabled": False,
                "assistKeytermsEnabled": True,
            }
        },
        headers=AUTH_HEADERS,
    )

    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "off"
    assert body["reason"] == "assist_summary_disabled"
    assert body["summary"] == ""
    assert body["key_terms"] == []
    assert body["evidence"] == []


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_returns_feature_disabled_when_env_flag_off(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Summary endpoint should hard-stop when the env kill switch is off."""
    monkeypatch.setattr(settings, "lecture_live_summary_enabled", False)

    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "統計学基礎",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    await async_client.post(
        "/api/v4/settings/me",
        json={"settings": {"assistSummaryEnabled": True}},
        headers=AUTH_HEADERS,
    )

    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "off"
    assert body["reason"] == "feature_disabled"


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_uses_cache_until_force_rebuild(
    async_client: AsyncClient,
    mock_summary_generator: Mock,
) -> None:
    """Repeated summary fetches should reuse the cached window unless forced."""
    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "統計学基礎",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    await async_client.post(
        "/api/v4/settings/me",
        json={"settings": {"assistSummaryEnabled": True}},
        headers=AUTH_HEADERS,
    )
    await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 1000,
            "end_ms": 5000,
            "text": "キャッシュ確認用の字幕です。",
            "confidence": 0.95,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )

    first = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=AUTH_HEADERS,
    )
    second = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=AUTH_HEADERS,
    )
    forced = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id, "force_rebuild": "true"},
        headers=AUTH_HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert forced.status_code == 200
    assert mock_summary_generator.generate_summary.await_count == 2


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
async def test_get_lecture_summary_latest_with_runtime_error_returns_503(
    async_client: AsyncClient,
) -> None:
    """Summary latest should map backend runtime errors to 503."""
    from app.api.v4.lecture import get_lecture_summary_service

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
        "/api/v4/settings/me",
        json={
            "settings": {
                "assistSummaryEnabled": True,
                "assistKeytermsEnabled": True,
            }
        },
        headers=AUTH_HEADERS,
    )

    class FailingSummaryService:
        async def get_latest_summary(
            self,
            session_id: str,
            user_id: str,
            force_rebuild: bool = False,
        ) -> None:
            del session_id, user_id, force_rebuild
            raise RuntimeError("summary backend down")

        async def rebuild_windows(self, session_id: str, user_id: str) -> int:
            del session_id, user_id
            return 0

    app.dependency_overrides[get_lecture_summary_service] = FailingSummaryService
    try:
        response = await async_client.get(
            "/api/v4/lecture/summary/latest",
            params={"session_id": session_id},
            headers=AUTH_HEADERS,
        )
    finally:
        app.dependency_overrides.pop(get_lecture_summary_service, None)

    body = response.json()
    assert response.status_code == 503
    assert body["error"]["code"] == "http_error"
    assert body["error"]["message"] == "Lecture summary backend is unavailable."


@pytest.mark.asyncio
async def test_post_transcript_analyze_keyterms_returns_off_when_keyterms_disabled(
    async_client: AsyncClient,
) -> None:
    """Key terms endpoint should return off when assist key terms is disabled."""
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
        "/api/v4/settings/me",
        json={
            "settings": {
                "assistSummaryEnabled": True,
                "assistKeytermsEnabled": False,
            }
        },
        headers=AUTH_HEADERS,
    )

    response = await async_client.post(
        "/api/v4/lecture/transcript/analyze-keyterms",
        json={
            "session_id": session_id,
            "transcript_text": "外れ値を検出します。",
            "lang_mode": "ja",
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "off"
    assert body["reason"] == "assist_keyterms_disabled"
    assert body["key_terms"] == []
    assert body["detected_terms"] == []


@pytest.mark.asyncio
async def test_post_transcript_analyze_keyterms_returns_feature_disabled_when_env_flag_off(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Key terms endpoint should hard-stop when the env kill switch is off."""
    monkeypatch.setattr(settings, "lecture_live_keyterms_enabled", False)

    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "統計学基礎",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    await async_client.post(
        "/api/v4/settings/me",
        json={"settings": {"assistKeytermsEnabled": True}},
        headers=AUTH_HEADERS,
    )

    response = await async_client.post(
        "/api/v4/lecture/transcript/analyze-keyterms",
        json={
            "session_id": session_id,
            "transcript_text": "外れ値を検出します。",
            "lang_mode": "ja",
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "off"
    assert body["reason"] == "feature_disabled"


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_respects_demo_user_alias_for_settings(
    async_client: AsyncClient,
) -> None:
    """Summary settings should apply across demo_user/demo-user aliases."""
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
        "/api/v4/settings/me",
        json={
            "settings": {
                "assistSummaryEnabled": False,
                "assistKeytermsEnabled": True,
            }
        },
        headers=AUTH_HEADERS,
    )

    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=LEGACY_DEMO_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "off"
    assert body["reason"] == "assist_summary_disabled"


@pytest.mark.asyncio
async def test_post_transcript_analyze_keyterms_respects_demo_user_alias_for_settings(
    async_client: AsyncClient,
) -> None:
    """Key terms settings should apply across demo_user/demo-user aliases."""
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
        "/api/v4/settings/me",
        json={
            "settings": {
                "assistSummaryEnabled": True,
                "assistKeytermsEnabled": False,
            }
        },
        headers=AUTH_HEADERS,
    )

    response = await async_client.post(
        "/api/v4/lecture/transcript/analyze-keyterms",
        json={
            "session_id": session_id,
            "transcript_text": "外れ値を検出します。",
            "lang_mode": "ja",
        },
        headers=LEGACY_DEMO_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "off"
    assert body["reason"] == "assist_keyterms_disabled"


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
async def test_post_lecture_session_finalize_with_runtime_error_still_finalizes(
    async_client: AsyncClient,
) -> None:
    """Finalize should degrade gracefully when summary backend is down."""
    from app.api.v4.lecture import get_lecture_summary_service

    class FailingSummaryService:
        async def get_latest_summary(self, session_id: str, user_id: str) -> None:
            del session_id, user_id
            raise RuntimeError("summary backend down")

        async def rebuild_windows(self, session_id: str, user_id: str) -> int:
            del session_id, user_id
            raise RuntimeError("summary backend down")

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

    app.dependency_overrides[get_lecture_summary_service] = FailingSummaryService
    try:
        response = await async_client.post(
            "/api/v4/lecture/session/finalize",
            json={"session_id": session_id, "build_qa_index": False},
            headers=AUTH_HEADERS,
        )
    finally:
        app.dependency_overrides.pop(get_lecture_summary_service, None)

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "finalized"
    assert body["session_id"] == session_id


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
async def test_post_lecture_session_finalize_uses_session_event_window_range(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Finalize should rebuild summary windows based on session event range."""
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
            "start_ms": 1_770_000_000_000,
            "end_ms": 1_770_000_005_000,
            "text": "序盤の説明です。",
            "confidence": 0.93,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )
    await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 1_770_000_070_000,
            "end_ms": 1_770_000_095_000,
            "text": "終盤の説明です。",
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
    assert body["status"] == "finalized"
    assert body["stats"]["summary_windows"] == 5

    async with session_factory() as session:
        summary_count_result = await session.execute(
            select(SummaryWindow).where(SummaryWindow.session_id == session_id)
        )
        summary_windows = list(summary_count_result.scalars().all())

    assert len(summary_windows) == 5
    assert min(window.start_ms for window in summary_windows) > 1_000_000_000_000


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


@pytest.mark.asyncio
async def test_post_lecture_session_finalize_accepts_legacy_live_status(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Finalize endpoint should accept legacy sessions with status=live."""
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

    async with session_factory() as session:
        result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        lecture_session = result.scalar_one()
        lecture_session.status = "live"
        await session.commit()

    response = await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={"session_id": session_id, "build_qa_index": False},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "finalized"


@pytest.mark.asyncio
async def test_post_lecture_session_finalize_accepts_demo_user_alias_headers(
    async_client: AsyncClient,
) -> None:
    """Finalize should succeed even when start/finalize requests use demo user aliases."""
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
        headers=LEGACY_DEMO_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    response = await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={"session_id": session_id, "build_qa_index": False},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "finalized"


@pytest.mark.asyncio
async def test_delete_lecture_session_returns_200_and_removes_records(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Delete endpoint should remove finalized session and related records."""
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

    chunk_response = await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 15000,
            "end_ms": 22000,
            "text": "削除テスト用イベント。",
            "confidence": 0.93,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )
    event_id = chunk_response.json()["event_id"]

    async with session_factory() as session:
        session.add(
            SpeechReviewHistory(
                session_id=session_id,
                speech_event_id=event_id,
                attempt_no=1,
                review_status="reviewed",
                input_text="削除テスト用イベント。",
                candidate_text="削除テスト用イベント。",
                final_text="削除テスト用イベント。",
                was_corrected=False,
                failure_reason=None,
                judge_model="test-judge",
                judge_confidence=0.9,
            )
        )
        await session.commit()

    await async_client.post(
        "/api/v4/lecture/session/finalize",
        json={"session_id": session_id, "build_qa_index": False},
        headers=AUTH_HEADERS,
    )

    response = await async_client.delete(
        f"/api/v4/lecture/session/{session_id}",
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["status"] == "deleted"
    assert body["auto_finalized"] is False

    async with session_factory() as session:
        session_result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        speech_result = await session.execute(
            select(SpeechEvent).where(SpeechEvent.session_id == session_id)
        )
        review_result = await session.execute(
            select(SpeechReviewHistory).where(
                SpeechReviewHistory.session_id == session_id
            )
        )

    assert session_result.scalar_one_or_none() is None
    assert speech_result.scalars().all() == []
    assert review_result.scalars().all() == []


@pytest.mark.asyncio
async def test_delete_lecture_session_auto_finalizes_live_session(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Delete endpoint should auto-finalize active/live session before deletion."""
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

    response = await async_client.delete(
        f"/api/v4/lecture/session/{session_id}",
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "deleted"
    assert body["auto_finalized"] is True

    async with session_factory() as session:
        session_result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
    assert session_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_lecture_session_removes_related_qa_turns(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Delete endpoint should remove lecture QA turn rows for the session."""
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
        session.add(
            QATurn(
                id=f"qa_turn_{session_id}",
                session_id=session_id,
                feature="lecture_qa",
                question="削除テストの質問",
                answer="削除テストの回答",
                confidence="high",
                citations_json=[],
                retrieved_chunk_ids_json=[],
                latency_ms=1,
                verifier_supported=True,
                outcome_reason="verified",
            )
        )
        await session.commit()

    response = await async_client.delete(
        f"/api/v4/lecture/session/{session_id}",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200

    async with session_factory() as session:
        qa_turn_result = await session.execute(
            select(QATurn).where(QATurn.session_id == session_id)
        )
    assert qa_turn_result.scalars().all() == []


@pytest.mark.asyncio
async def test_delete_lecture_session_accepts_legacy_ended_status(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Delete endpoint should remove legacy ended session rows."""
    session_id = "lec_legacy_ended_001"
    async with session_factory() as session:
        session.add(
            LectureSession(
                id=session_id,
                user_id="demo_user",
                course_id=None,
                course_name="統計学基礎",
                lang_mode="ja",
                status="ended",
                camera_enabled=True,
                slide_roi=[100, 80, 900, 520],
                board_roi=[80, 560, 920, 980],
                consent_acknowledged=True,
            )
        )
        await session.commit()

    response = await async_client.delete(
        f"/api/v4/lecture/session/{session_id}",
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["status"] == "deleted"
    assert body["auto_finalized"] is False

    async with session_factory() as session:
        session_result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
    assert session_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_lecture_session_for_other_user_returns_404(
    async_client: AsyncClient,
) -> None:
    """Delete endpoint should enforce ownership."""
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

    response = await async_client.delete(
        f"/api/v4/lecture/session/{session_id}",
        headers=OWNER_B_HEADERS,
    )
    assert response.status_code == 404


# ============================================================================
# Azure OpenAI Summary Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_with_azure_openai_returns_200(
    async_client: AsyncClient,
    mocker: Mock,
) -> None:
    """Summary endpoint with Azure OpenAI should return LLM-generated summary."""
    # Mock Azure OpenAI response
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": '{"summary": "Azure OpenAI で生成された要約", "key_terms": ["外れ値"], "evidence": []}'
                }
            }
        ]
    }

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    http_response = mocker.MagicMock()
    http_response.read.return_value = json.dumps(mock_response).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = http_response

    # Start session and add events
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

    # Get summary with Azure OpenAI
    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert "summary" in body
    assert "key_terms" in body
    assert "evidence" in body


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_with_azure_disabled_uses_deterministic(
    async_client: AsyncClient,
) -> None:
    """Summary without Azure OpenAI should use deterministic fallback."""
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
        "/api/v4/settings/me",
        json={
            "settings": {
                "assistSummaryEnabled": True,
                "assistKeytermsEnabled": True,
            }
        },
        headers=AUTH_HEADERS,
    )

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

    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["summary"] != ""
    assert body["status"] in ["ok", "no_data"]


@pytest.mark.asyncio
async def test_get_lecture_summary_latest_ownership_enforced_with_azure(
    async_client: AsyncClient,
    mocker: Mock,
) -> None:
    """Ownership validation should work with Azure OpenAI enabled."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": '{"summary": "要約", "key_terms": [], "evidence": []}'
                }
            }
        ]
    }

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    http_response = mocker.MagicMock()
    http_response.read.return_value = json.dumps(mock_response).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = http_response

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

    await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 15000,
            "end_ms": 22000,
            "text": "テスト",
            "confidence": 0.93,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=OWNER_A_HEADERS,
    )

    response = await async_client.get(
        "/api/v4/lecture/summary/latest",
        params={"session_id": session_id},
        headers=OWNER_B_HEADERS,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_lecture_session_lang_mode_updates_active_session(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """PATCH /lecture/session/lang-mode should update persisted lang_mode."""
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

    response = await async_client.patch(
        "/api/v4/lecture/session/lang-mode",
        json={"session_id": session_id, "lang_mode": "easy-ja"},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["lang_mode"] == "easy-ja"
    assert body["status"] == "active"

    async with session_factory() as session:
        result = await session.execute(
            select(LectureSession).where(LectureSession.id == session_id)
        )
        lecture_session = result.scalar_one()
    assert lecture_session.lang_mode == "easy-ja"


@pytest.mark.asyncio
async def test_post_lecture_subtitle_transform_returns_transformed_text(
    async_client: AsyncClient,
) -> None:
    """POST /lecture/subtitle/transform should return transformed subtitle text."""
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
        "/api/v4/lecture/subtitle/transform",
        json={
            "session_id": session_id,
            "text": "機械学習は未知データで性能を確認します。",
            "target_lang_mode": "easy-ja",
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["target_lang_mode"] == "easy-ja"
    assert isinstance(body["transformed_text"], str)
    assert body["transformed_text"].strip() != ""
    assert body["status"] in {"translated", "fallback"}
    if body["status"] == "fallback":
        assert isinstance(body["fallback_reason"], str)
        assert body["fallback_reason"]
    else:
        assert body["fallback_reason"] is None


@pytest.mark.asyncio
async def test_post_lecture_subtitle_transform_returns_passthrough_for_ja(
    async_client: AsyncClient,
) -> None:
    """POST /lecture/subtitle/transform should passthrough ja mode."""
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
    source_text = "この式は分散の定義です。"

    response = await async_client.post(
        "/api/v4/lecture/subtitle/transform",
        json={
            "session_id": session_id,
            "text": source_text,
            "target_lang_mode": "ja",
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["target_lang_mode"] == "ja"
    assert body["transformed_text"] == source_text
    assert body["status"] == "passthrough"
    assert body["fallback_reason"] is None


@pytest.mark.asyncio
async def test_post_lecture_subtitle_transform_returns_feature_disabled_when_flag_off(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subtitle transform should fail closed when translation is disabled."""
    from app.api.v4.lecture import get_caption_transform_service

    monkeypatch.setattr(settings, "lecture_live_translation_enabled", False)
    app.dependency_overrides.pop(get_caption_transform_service, None)

    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "統計学基礎",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    response = await async_client.post(
        "/api/v4/lecture/subtitle/transform",
        json={
            "session_id": session_id,
            "text": "機械学習は未知データで性能を確認します。",
            "target_lang_mode": "en",
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "fallback"
    assert body["fallback_reason"] == "feature_disabled"


@pytest.mark.asyncio
async def test_post_lecture_subtitle_audit_returns_corrected_text(
    async_client: AsyncClient,
) -> None:
    """POST /lecture/subtitle/audit should return corrected subtitle text."""
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
    source_text = "機械学習わ未知データで性能お確認します。"

    response = await async_client.post(
        "/api/v4/lecture/subtitle/audit",
        json={
            "session_id": session_id,
            "text": source_text,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["original_text"] == source_text
    assert isinstance(body["corrected_text"], str)
    assert body["corrected_text"].strip() != ""
    assert body["review_status"] in {"reviewed", "review_failed"}
    assert isinstance(body["reviewed"], bool)
    assert isinstance(body["was_corrected"], bool)
    assert isinstance(body["retry_count"], int)


@pytest.mark.asyncio
async def test_post_lecture_speech_chunk_audit_apply_updates_persisted_text(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """POST /lecture/speech/chunk/audit-apply should replace subtitle text."""
    # Override correction + judge dependencies with deterministic fakes
    from app.api.v4.lecture import (
        get_japanese_asr_correction_service,
        get_japanese_asr_hallucination_judge_service,
    )
    from app.services.asr_hallucination_judge_service import (
        NoopJapaneseASRHallucinationJudgeService,
    )

    class _FakeCorrector:
        async def correct_minimally(self, text: str) -> str:
            return text.replace("わ", "は").replace("お", "を")

    app.dependency_overrides[get_japanese_asr_correction_service] = _FakeCorrector
    app.dependency_overrides[get_japanese_asr_hallucination_judge_service] = (
        NoopJapaneseASRHallucinationJudgeService
    )

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

    ingest_response = await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 0,
            "end_ms": 4000,
            "text": "機械学習わ未知データで性能お確認します。",
            "confidence": 0.91,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )
    event_id = ingest_response.json()["event_id"]

    response = await async_client.post(
        "/api/v4/lecture/speech/chunk/audit-apply",
        json={
            "session_id": session_id,
            "event_id": event_id,
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["event_id"] == event_id
    assert body["updated"] is True
    assert body["review_status"] == "reviewed"
    assert body["reviewed"] is True
    assert body["was_corrected"] is True
    assert body["corrected_text"].strip() != ""

    async with session_factory() as session:
        result = await session.execute(
            select(SpeechEvent).where(SpeechEvent.id == event_id)
        )
        speech_event = result.scalar_one()
    assert speech_event.original_text == "機械学習わ未知データで性能お確認します。"
    assert speech_event.text == body["corrected_text"]


@pytest.mark.asyncio
async def test_post_lecture_speech_chunk_audit_apply_returns_feature_disabled_when_flag_off(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit-apply should no-op when ASR review is disabled."""
    monkeypatch.setattr(settings, "lecture_live_asr_review_enabled", False)

    start_response = await async_client.post(
        "/api/v4/lecture/session/start",
        json={
            "course_name": "統計学基礎",
            "course_id": None,
            "lang_mode": "ja",
            "camera_enabled": True,
            "slide_roi": [100, 80, 900, 520],
            "board_roi": [80, 560, 920, 980],
            "consent_acknowledged": True,
        },
        headers=AUTH_HEADERS,
    )
    session_id = start_response.json()["session_id"]

    ingest_response = await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 0,
            "end_ms": 4000,
            "text": "機械学習わ未知データで性能お確認します。",
            "confidence": 0.91,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )
    event_id = ingest_response.json()["event_id"]

    response = await async_client.post(
        "/api/v4/lecture/speech/chunk/audit-apply",
        json={"session_id": session_id, "event_id": event_id},
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["updated"] is False
    assert body["reviewed"] is False
    assert body["was_corrected"] is False
    assert body["failure_reason"] == "feature_disabled"


@pytest.mark.asyncio
async def test_post_lecture_speech_chunk_audit_apply_with_unknown_event_returns_404(
    async_client: AsyncClient,
) -> None:
    """Audit-apply endpoint should return 404 for unknown speech event."""
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
        "/api/v4/lecture/speech/chunk/audit-apply",
        json={
            "session_id": session_id,
            "event_id": "missing-event-id",
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_get_lecture_events_stream_once_reflects_updated_speech_text(
    async_client: AsyncClient,
) -> None:
    """SSE snapshot should return corrected text after audit-apply update."""
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

    ingest_response = await async_client.post(
        "/api/v4/lecture/speech/chunk",
        json={
            "session_id": session_id,
            "start_ms": 0,
            "end_ms": 4000,
            "text": "機械学習わ未知データで性能お確認します。",
            "confidence": 0.91,
            "is_final": True,
            "speaker": "teacher",
        },
        headers=AUTH_HEADERS,
    )
    event_id = ingest_response.json()["event_id"]

    audit_response = await async_client.post(
        "/api/v4/lecture/speech/chunk/audit-apply",
        json={"session_id": session_id, "event_id": event_id},
        headers=AUTH_HEADERS,
    )
    corrected_text = audit_response.json()["corrected_text"]

    response = await async_client.get(
        "/api/v4/lecture/events/stream",
        params={"session_id": session_id, "once": "true"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    transcript_events = [e for e in events if e.get("type") == "transcript.final"]
    assert transcript_events
    transcript_payload = transcript_events[0]["payload"]
    assert transcript_payload["id"] == event_id
    assert transcript_payload["sourceLangText"] == corrected_text
    assert (
        transcript_payload.get("originalLangText")
        or transcript_payload["sourceLangText"]
    ) == "機械学習わ未知データで性能お確認します。"


@pytest.mark.asyncio
async def test_post_lecture_subtitle_transform_returns_en_text(
    async_client: AsyncClient,
) -> None:
    """POST /lecture/subtitle/transform should support English target mode."""
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
    source_text = "機械学習は未知データで性能を確認します。"

    response = await async_client.post(
        "/api/v4/lecture/subtitle/transform",
        json={
            "session_id": session_id,
            "text": source_text,
            "target_lang_mode": "en",
        },
        headers=AUTH_HEADERS,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_id"] == session_id
    assert body["target_lang_mode"] == "en"
    assert isinstance(body["transformed_text"], str)
    assert body["transformed_text"].strip() != ""
    assert body["transformed_text"] != source_text
    assert body["status"] in {"translated", "fallback"}
    if body["status"] == "fallback":
        assert isinstance(body["fallback_reason"], str)
        assert body["fallback_reason"]
    else:
        assert body["fallback_reason"] is None

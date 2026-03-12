"""Unit tests for timestamp column definitions."""

from sqlalchemy import BigInteger

from app.models.lecture_chunk import LectureChunk
from app.models.speech_event import SpeechEvent
from app.models.summary_window import SummaryWindow
from app.models.visual_event import VisualEvent


def test_speech_event_timestamp_columns_use_bigint() -> None:
    """Speech event timestamps should be stored as bigint."""
    assert isinstance(SpeechEvent.__table__.c.start_ms.type, BigInteger)
    assert isinstance(SpeechEvent.__table__.c.end_ms.type, BigInteger)


def test_summary_window_timestamp_columns_use_bigint() -> None:
    """Summary window timestamps should be stored as bigint."""
    assert isinstance(SummaryWindow.__table__.c.start_ms.type, BigInteger)
    assert isinstance(SummaryWindow.__table__.c.end_ms.type, BigInteger)


def test_lecture_chunk_timestamp_columns_use_bigint() -> None:
    """Lecture chunk timestamps should be stored as bigint."""
    assert isinstance(LectureChunk.__table__.c.start_ms.type, BigInteger)
    assert isinstance(LectureChunk.__table__.c.end_ms.type, BigInteger)


def test_visual_event_timestamp_column_uses_bigint() -> None:
    """Visual event timestamps should be stored as bigint."""
    assert isinstance(VisualEvent.__table__.c.timestamp_ms.type, BigInteger)

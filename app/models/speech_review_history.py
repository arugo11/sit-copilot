"""Speech review audit history for subtitle correction decisions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

__all__ = ["SpeechReviewHistory"]

if TYPE_CHECKING:
    from app.models.lecture_session import LectureSession
    from app.models.speech_event import SpeechEvent


class SpeechReviewHistory(Base):
    """ORM model for per-attempt speech subtitle review audit history."""

    __tablename__ = "speech_review_histories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("lecture_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speech_event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("speech_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    was_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    judge_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    session: Mapped[LectureSession] = relationship(
        "LectureSession",
        back_populates="speech_review_histories",
    )
    speech_event: Mapped[SpeechEvent] = relationship("SpeechEvent", back_populates="review_histories")

    __table_args__ = (
        Index("ix_speech_review_histories_event_created", "speech_event_id", "created_at"),
    )

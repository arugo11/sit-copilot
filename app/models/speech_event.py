"""SpeechEvent ORM model for finalized subtitle events."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

__all__ = ["SpeechEvent"]

if TYPE_CHECKING:
    from app.models.lecture_session import LectureSession
    from app.models.speech_review_history import SpeechReviewHistory


class SpeechEvent(Base):
    """ORM model for per-chunk speech transcription metadata."""

    __tablename__ = "speech_events"

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
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False)
    speaker: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    session: Mapped[LectureSession] = relationship(
        "LectureSession",
        back_populates="speech_events",
    )
    review_histories: Mapped[list[SpeechReviewHistory]] = relationship(
        "SpeechReviewHistory",
        back_populates="speech_event",
        cascade="all, delete-orphan",
    )

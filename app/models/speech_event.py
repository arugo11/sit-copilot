"""SpeechEvent ORM model for finalized subtitle events."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

__all__ = ["SpeechEvent"]

if TYPE_CHECKING:
    from app.models.lecture_session import LectureSession


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
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
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

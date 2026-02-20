"""LectureSession ORM model for live lecture sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

__all__ = ["LectureSession"]

if TYPE_CHECKING:
    from app.models.lecture_chunk import LectureChunk
    from app.models.speech_event import SpeechEvent
    from app.models.summary_window import SummaryWindow
    from app.models.visual_event import VisualEvent


class LectureSession(Base):
    """ORM model for a lecture live session lifecycle."""

    __tablename__ = "lecture_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    course_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    lang_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="ja")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    camera_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    slide_roi: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    board_roi: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    qa_index_built: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    speech_events: Mapped[list[SpeechEvent]] = relationship(
        "SpeechEvent",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    visual_events: Mapped[list[VisualEvent]] = relationship(
        "VisualEvent",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    summary_windows: Mapped[list[SummaryWindow]] = relationship(
        "SummaryWindow",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    lecture_chunks: Mapped[list[LectureChunk]] = relationship(
        "LectureChunk",
        back_populates="session",
        cascade="all, delete-orphan",
    )

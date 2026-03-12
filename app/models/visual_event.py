"""VisualEvent ORM model for OCR events from lecture camera ROI."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

__all__ = ["VisualEvent"]

if TYPE_CHECKING:
    from app.models.lecture_session import LectureSession


class VisualEvent(Base):
    """ORM model for per-frame OCR metadata events."""

    __tablename__ = "visual_events"

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
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    quality: Mapped[str] = mapped_column(String(16), nullable=False)
    change_score: Mapped[float] = mapped_column(Float, nullable=False)
    blob_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    session: Mapped[LectureSession] = relationship(
        "LectureSession",
        back_populates="visual_events",
    )

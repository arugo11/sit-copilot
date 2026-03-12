"""SummaryWindow ORM model for lecture 30-second summaries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

__all__ = ["SummaryWindow"]

if TYPE_CHECKING:
    from app.models.lecture_session import LectureSession


class SummaryWindow(Base):
    """ORM model for persisted lecture summary windows."""

    __tablename__ = "summary_windows"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "start_ms",
            "end_ms",
            name="uq_summary_windows_session_window",
        ),
    )

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
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    key_terms_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence_event_ids_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    session: Mapped[LectureSession] = relationship(
        "LectureSession",
        back_populates="summary_windows",
    )

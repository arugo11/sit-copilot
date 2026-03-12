"""LectureChunk ORM model for finalized lecture search artifacts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

__all__ = ["LectureChunk"]

if TYPE_CHECKING:
    from app.models.lecture_session import LectureSession


class LectureChunk(Base):
    """ORM model for persisted lecture chunks used for QA indexing."""

    __tablename__ = "lecture_chunks"

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
    chunk_type: Mapped[str] = mapped_column(String(16), nullable=False)
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    speech_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    indexed_to_search: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    session: Mapped[LectureSession] = relationship(
        "LectureSession",
        back_populates="lecture_chunks",
    )

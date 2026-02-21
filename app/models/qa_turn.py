"""QATurn ORM model for lecture/procedure QA history."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

__all__ = ["QATurn"]


class QATurn(Base):
    """ORM model for storing QA interaction history."""

    __tablename__ = "qa_turns"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    feature: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    retrieved_chunk_ids_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    verifier_supported: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    outcome_reason: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unspecified",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

"""User ORM model for settings ownership."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

__all__ = ["User"]


class User(Base):
    """ORM model representing an application user."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Demo User",
    )
    preferred_lang: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="ja",
    )
    ui_preset: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="standard",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
    )

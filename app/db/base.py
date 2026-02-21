"""SQLAlchemy DeclarativeBase for ORM models."""

from sqlalchemy.orm import DeclarativeBase

__all__ = ["Base"]


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass

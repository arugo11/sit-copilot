"""API v4 route modules."""

from app.api.v4 import health, lecture, lecture_qa, procedure, settings

__all__ = ["health", "settings", "procedure", "lecture", "lecture_qa"]

"""API v4 route modules."""

from app.api.v4 import auth, health, lecture, lecture_qa, procedure, readiness, settings

__all__ = [
    "auth",
    "health",
    "settings",
    "procedure",
    "lecture",
    "lecture_qa",
    "readiness",
]

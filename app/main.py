"""FastAPI application main entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v4 import health as health_api
from app.api.v4 import lecture as lecture_api
from app.api.v4 import lecture_qa as lecture_qa_api
from app.api.v4 import procedure as procedure_api
from app.api.v4 import readiness as readiness_api
from app.api.v4 import settings as settings_api
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.db.base import Base
from app.db.session import engine
from app.models import (  # noqa: F401  # Ensure model metadata is loaded
    LectureChunk,
    LectureSession,
    QATurn,
    SpeechEvent,
    SummaryWindow,
    User,
    UserSettings,
    VisualEvent,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create database tables at app startup for demo single-replica usage."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan,
)
register_error_handlers(app)

# Include v4 API routers
app.include_router(health_api.router, prefix="/api/v4")
app.include_router(settings_api.router, prefix="/api/v4")
app.include_router(procedure_api.router, prefix="/api/v4")
app.include_router(lecture_api.router, prefix="/api/v4")
app.include_router(lecture_qa_api.router, prefix="/api/v4")
app.include_router(readiness_api.router, prefix="/api/v4")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "SIT Copilot API"}


# Include v4 API router (will be added by API-Implementer)
# from app.api.v4 import router as v4_router
# app.include_router(v4_router, prefix="/api/v4")

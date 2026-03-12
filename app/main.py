"""FastAPI application main entry point."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v4 import auth as auth_api
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
    SpeechReviewHistory,
    SummaryWindow,
    User,
    UserSettings,
    VisualEvent,
)
from app.services.observability import (
    NoopWeaveObserverService,
    WandBWeaveObserverService,
    WeaveDispatcher,
)

logger = logging.getLogger(__name__)
POSTGRES_BIGINT_TIMESTAMP_COLUMNS: tuple[tuple[str, str], ...] = (
    ("speech_events", "start_ms"),
    ("speech_events", "end_ms"),
    ("summary_windows", "start_ms"),
    ("summary_windows", "end_ms"),
    ("lecture_chunks", "start_ms"),
    ("lecture_chunks", "end_ms"),
    ("visual_events", "timestamp_ms"),
)


async def _ensure_sqlite_schema_compatibility(connection) -> None:  # noqa: ANN001
    """Apply lightweight SQLite compatibility migrations for demo runtime."""
    if not settings.database_url.startswith("sqlite"):
        return

    result = await connection.exec_driver_sql("PRAGMA table_info(speech_events)")
    columns = {str(row[1]) for row in result.fetchall()}
    if "original_text" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE speech_events ADD COLUMN original_text TEXT"
        )


async def _get_postgresql_column_udt_name(
    connection, table_name: str, column_name: str  # noqa: ANN001
) -> str | None:
    result = await connection.exec_driver_sql(
        """
        SELECT c.udt_name
        FROM information_schema.columns AS c
        WHERE c.table_schema = current_schema()
          AND c.table_name = :table_name
          AND c.column_name = :column_name
        """,
        {"table_name": table_name, "column_name": column_name},
    )
    row = result.first()
    if row is None:
        return None
    return str(row[0]).strip().lower() or None


async def _ensure_postgresql_bigint_timestamp_columns(connection) -> None:  # noqa: ANN001
    """Promote PostgreSQL timestamp-ms columns from int4 to int8."""
    if connection.dialect.name != "postgresql":
        return

    for table_name, column_name in POSTGRES_BIGINT_TIMESTAMP_COLUMNS:
        udt_name = await _get_postgresql_column_udt_name(
            connection,
            table_name,
            column_name,
        )
        if udt_name is None:
            logger.info(
                "postgres_bigint_timestamp_column_missing table=%s column=%s",
                table_name,
                column_name,
            )
            continue
        if udt_name == "int8":
            logger.info(
                "postgres_bigint_timestamp_column_ok table=%s column=%s",
                table_name,
                column_name,
            )
            continue
        if udt_name != "int4":
            logger.warning(
                "postgres_bigint_timestamp_column_unexpected_type table=%s column=%s udt_name=%s",
                table_name,
                column_name,
                udt_name,
            )
            continue

        await connection.exec_driver_sql(
            f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE BIGINT"
        )
        logger.info(
            "postgres_bigint_timestamp_column_migrated table=%s column=%s",
            table_name,
            column_name,
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create database tables at app startup for demo single-replica usage.

    Also initializes Weave observer service if enabled.
    """
    if not settings.azure_openai_enabled:
        logger.warning(
            "azure_openai_disabled env=AZURE_OPENAI_ENABLED|AZURE_OPENAI_ENABLE feature_flags=subtitle_audit,caption_transform,summary,qa fallback_mode=local"
        )

    # Initialize Weave observer
    weave_observer = NoopWeaveObserverService()

    if settings.weave.enabled:
        try:
            import weave

            weave_client = weave.init(project_name=settings.weave.project)
            weave_observer = WandBWeaveObserverService(settings.weave)
            # Start dispatcher
            dispatcher: WeaveDispatcher | None = getattr(
                weave_observer, "_dispatcher_value", None
            )
            if dispatcher is not None:
                await dispatcher.start()
            logger.info(f"Weave initialized: project={settings.weave.project}")

            # Register gpt-5-nano custom costs for Metrics monitoring
            # Azure OpenAI Global Standard pricing (USD per 1M tokens)
            #   Input:  $0.05 → $0.00000005 per token
            #   Output: $0.40 → $0.0000004  per token
            try:
                from datetime import UTC, datetime

                weave_client.add_cost(
                    llm_id="gpt-5-nano",
                    prompt_token_cost=0.05 / 1_000_000,
                    completion_token_cost=0.40 / 1_000_000,
                    effective_date=datetime(2025, 1, 1, tzinfo=UTC),
                )
                logger.info("weave_custom_cost_registered model=gpt-5-nano")
            except Exception as cost_err:
                logger.debug(
                    "weave_cost_registration_skipped reason=%s", cost_err
                )
        except Exception as e:
            logger.warning(f"Weave initialization failed: {e}. Using Noop.")
            weave_observer = NoopWeaveObserverService()

    # Store observer in app state for dependency injection
    app.state.weave_observer = weave_observer

    # Initialize database
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await _ensure_sqlite_schema_compatibility(connection)
        await _ensure_postgresql_bigint_timestamp_columns(connection)
        if settings.database_url.startswith("sqlite"):
            await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            await connection.exec_driver_sql("PRAGMA busy_timeout=30000")
            await connection.exec_driver_sql("PRAGMA synchronous=NORMAL")

    yield

    # Shutdown: stop Weave dispatcher
    dispatcher = getattr(weave_observer, "_dispatcher_value", None)
    if dispatcher is not None:
        await dispatcher.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan,
)


def _get_cors_allowed_origins() -> list[str]:
    """Resolve CORS allowed origins from environment with local defaults."""
    default_origins = [
        "http://127.0.0.1:4176",
        "http://localhost:4176",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if not configured:
        return default_origins
    if configured == "*":
        return ["*"]

    configured_origins = [
        origin.strip() for origin in configured.split(",") if origin.strip()
    ]
    merged = [*default_origins]
    for origin in configured_origins:
        if origin not in merged:
            merged.append(origin)
    return merged


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

# Include v4 API routers
app.include_router(health_api.router, prefix="/api/v4")
app.include_router(auth_api.router, prefix="/api/v4")
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

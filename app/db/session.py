"""Async database session management."""

import asyncio
import logging
from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

__all__ = [
    "engine",
    "AsyncSessionFactory",
    "commit_with_retry",
    "get_db",
    "is_sqlite_locked_error",
]

logger = logging.getLogger(__name__)

_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs: dict[str, object] = {
    "echo": False,
}
if _is_sqlite:
    # For SQLite: allow Python-level retry for up to 30 s on busy/locked DB.
    _engine_kwargs["connect_args"] = {"timeout": 30}
    # Keep connections short-lived to reduce lock retention/cross-request contention.
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(
    settings.database_url,
    **_engine_kwargs,
)


# ---- SQLite pragmas applied per-connection --------------------------------
if _is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, connection_record):  # noqa: ANN001
        """Enable WAL journal mode and busy-timeout for every connection.

        WAL allows concurrent readers and a single writer, which prevents the
        ``database is locked`` errors caused by SSE polling reads overlapping
        with write transactions (session start / finalize).
        """
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            logger.warning(
                "Failed to set SQLite PRAGMAs (database may be busy); "
                "will retry on next connection.",
                exc_info=True,
            )
        finally:
            cursor.close()


AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # REQUIRED: Prevents lazy loading errors after commit
)


def is_sqlite_locked_error(exc: Exception) -> bool:
    if not isinstance(exc, OperationalError):
        return False
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


async def commit_with_retry(
    session: AsyncSession,
    *,
    max_retries: int = 5,
    base_delay_seconds: float = 0.05,
) -> None:
    """Commit transaction with bounded retry for transient SQLite lock errors."""
    attempts = max(1, max_retries)
    for attempt in range(attempts):
        try:
            await session.commit()
            return
        except Exception as exc:
            if (
                not _is_sqlite
                or not is_sqlite_locked_error(exc)
                or attempt == attempts - 1
            ):
                await session.rollback()
                raise
            await session.rollback()
            delay = base_delay_seconds * (2**attempt)
            logger.warning(
                "SQLite lock detected during commit; retrying in %.3fs "
                "(attempt %d/%d)",
                delay,
                attempt + 1,
                attempts,
            )
            await asyncio.sleep(delay)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for database session with auto-commit.

    Yields:
        AsyncSession: Database session for the request lifecycle

    Example:
        @router.get("/settings")
        async def get_settings(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(UserSettings))
            return result.scalar_one_or_none()
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await commit_with_retry(session)  # Auto-commit on success
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

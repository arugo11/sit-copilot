"""Async database session management."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

__all__ = ["engine", "AsyncSessionFactory", "get_db"]

engine = create_async_engine(
    settings.database_url,
    echo=False,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # REQUIRED: Prevents lazy loading errors after commit
)


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
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

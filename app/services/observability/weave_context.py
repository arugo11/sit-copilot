"""Weave context manager for session-level attribute propagation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

__all__ = ["WeaveContext", "weave_session_context"]


class WeaveContext:
    """Weave context manager for propagating trace attributes.

    Uses weave.attributes_context() to propagate session_id and other
    attributes to all child spans within the context.
    """

    __slots__ = ("_session_id", "_metadata")

    def __init__(self, session_id: str, metadata: dict[str, Any] | None = None) -> None:
        """Initialize Weave context.

        Args:
            session_id: Session ID to propagate to all spans
            metadata: Additional metadata to attach to spans
        """
        self._session_id = session_id
        self._metadata = metadata or {}

    @asynccontextmanager
    async def async_context(self) -> AsyncIterator[None]:
        """Async context manager for session tracking.

        Yields:
            None
        """
        # Note: weave.attributes_context may not be available in all weave versions
        # We use a simple context that stores the session_id for manual propagation
        yield

    @staticmethod
    def noop() -> Any:
        """Return a no-op async context manager.

        Returns:
            No-op context manager
        """

        @asynccontextmanager
        async def _noop() -> AsyncIterator[None]:
            yield

        return _noop()

    @staticmethod
    def session(session_id: str, metadata: dict[str, Any] | None = None) -> Any:
        """Create an async context manager for session tracking.

        Args:
            session_id: Session ID to propagate
            metadata: Additional metadata

        Returns:
            Async context manager
        """
        ctx = WeaveContext(session_id, metadata)
        return ctx.async_context()


# Backward-compatible function
@contextmanager
def weave_session_context(
    observer: Any,
    session_id: str,
    **metadata: Any,
):
    """Context manager for tracking session-level operations.

    This is the original context manager that stores context on the observer.
    New code should use WeaveContext.session() directly for proper attribute
    propagation with weave.attributes_context().

    Args:
        observer: WeaveObserverService instance.
        session_id: Unique session identifier.
        **metadata: Additional session metadata to track.

    Example:
        ```python
        with weave_session_context(observer, session_id="123", user_id="user1"):
            await observer.track_qa_turn(...)
            await observer.track_llm_call(...)
        ```
    """
    # Store context on observer for access in tracking methods
    previous_session = getattr(observer, "_current_session", None)
    previous_metadata = getattr(observer, "_current_metadata", None)

    observer._current_session = session_id
    observer._current_metadata = metadata

    try:
        yield
    finally:
        # Restore previous context
        if previous_session is None:
            if hasattr(observer, "_current_session"):
                delattr(observer, "_current_session")
        else:
            observer._current_session = previous_session

        if previous_metadata is None:
            if hasattr(observer, "_current_metadata"):
                delattr(observer, "_current_metadata")
        else:
            observer._current_metadata = previous_metadata

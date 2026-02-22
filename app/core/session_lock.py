"""In-process locks for request write serialization."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

_lock_index_guard = asyncio.Lock()
_scoped_locks: dict[str, asyncio.Lock] = {}


async def _get_or_create_lock(scope: str, key: str) -> asyncio.Lock:
    normalized_key = key.strip()
    lock_name = f"{scope}:{normalized_key}"
    async with _lock_index_guard:
        lock = _scoped_locks.get(lock_name)
        if lock is None:
            lock = asyncio.Lock()
            _scoped_locks[lock_name] = lock
    return lock


@asynccontextmanager
async def session_write_lock(session_id: str) -> AsyncIterator[None]:
    """Serialize writes for the same lecture session within one app process."""
    lock = await _get_or_create_lock("session", session_id)
    async with lock:
        yield


@asynccontextmanager
async def user_write_lock(user_id: str) -> AsyncIterator[None]:
    """Serialize start writes for the same user within one app process."""
    lock = await _get_or_create_lock("user", user_id)
    async with lock:
        yield

"""Shared rate-limiting utilities for public demo endpoints."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Final

from fastapi import HTTPException, Request, status

RATE_LIMIT_WINDOW_SECONDS: Final[float] = 60.0


class SlidingWindowRateLimiter:
    """Simple in-memory sliding-window limiter."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(
        self,
        *,
        bucket: str,
        key: str,
        max_requests: int,
        window_seconds: float = RATE_LIMIT_WINDOW_SECONDS,
    ) -> bool:
        now = time.monotonic()
        threshold = now - window_seconds
        compound_key = f"{bucket}:{key}"

        async with self._lock:
            queue = self._events[compound_key]
            while queue and queue[0] < threshold:
                queue.popleft()

            if len(queue) >= max_requests:
                return False

            queue.append(now)
        return True


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    """Describes a per-minute request budget for one endpoint class."""

    bucket: str
    max_requests: int


def resolve_client_key(request: Request, *, user_id: str | None = None) -> str:
    """Return a stable best-effort rate-limit key."""
    if user_id:
        return f"user:{user_id}"
    if request.client and request.client.host:
        return f"ip:{request.client.host}"
    return "unknown"


async def enforce_rate_limit(
    request: Request,
    *,
    limiter: SlidingWindowRateLimiter,
    policy: RateLimitPolicy,
    user_id: str | None = None,
    detail: str = "Too many requests.",
) -> None:
    """Raise 429 when the policy is exceeded."""
    client_key = resolve_client_key(request, user_id=user_id)
    allowed = await limiter.allow(
        bucket=policy.bucket,
        key=client_key,
        max_requests=policy.max_requests,
    )
    if allowed:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
    )

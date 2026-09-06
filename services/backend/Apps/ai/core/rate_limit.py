"""
In-memory request rate limiting.

Protects the AI service — specifically the LLM-calling chat endpoint —
against being spammed with repeated requests, which would otherwise incur
unbounded LLM cost and load with no application-level defense (item 16 of
the Phase 14 AI-safety hardening audit: "repeated requests").

Scope and honesty about limits
-------------------------------
This is a single-process, in-memory fixed-window limiter keyed by the
caller's internal service API key — the only stable identity available to
this internal, Django-authenticated service; there is no per-end-user
identity at this layer. It resets on process restart and is **not** shared
across multiple running instances. A multi-instance deployment would need a
shared store (e.g. Redis); that gap is documented here rather than silently
papered over. For a single-instance deployment (the common case for an
internal microservice like this one) it is fully effective.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Deque, Dict, Optional

from fastapi import Request, status

from Apps.ai.core.config import get_settings
from Apps.ai.core.exceptions import AppException


class RateLimitExceededError(AppException):
    """The caller has exceeded the configured request rate."""

    def __init__(self, *, retry_after_seconds: float):
        super().__init__(
            message="Too many requests. Please slow down and retry shortly.",
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": round(max(0.0, retry_after_seconds), 3)},
        )
        self.retry_after_seconds = retry_after_seconds


class RateLimiter:
    """Fixed-window request counter, keyed by caller identity.

    Thread-safe (a single lock guards all state) so it is safe to share one
    instance across concurrent request handlers within a process.
    """

    def __init__(self, *, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str, *, now: Optional[float] = None) -> None:
        """Record one request for ``key`` and raise if it exceeds the window budget.

        Raises:
            RateLimitExceededError: ``key`` has made
                ``max_requests`` or more requests within the current window.
        """
        current_time = now if now is not None else time.monotonic()
        with self._lock:
            window = self._hits.setdefault(key, deque())
            cutoff = current_time - self._window_seconds
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= self._max_requests:
                # window may be empty here when max_requests <= 0 (no prior
                # hit to measure from); fall back to the full window length.
                oldest = window[0] if window else current_time
                retry_after = oldest + self._window_seconds - current_time
                raise RateLimitExceededError(retry_after_seconds=retry_after)
            window.append(current_time)

    def reset(self) -> None:
        """Clear all tracked state. Intended for testing only."""
        with self._lock:
            self._hits.clear()


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Return the process-wide rate limiter singleton, built from ``Settings``."""
    global _rate_limiter
    if _rate_limiter is None:
        settings = get_settings()
        _rate_limiter = RateLimiter(
            max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )
    return _rate_limiter


async def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing the configured rate limit.

    Keyed by the caller's ``X-API-Key`` header — the internal service
    identity — falling back to the client host if absent. Declared after
    ``verify_service_api_key`` on protected routers, so an unauthenticated
    request is rejected before it can consume rate-limit budget.
    """
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED:
        return
    api_key = request.headers.get("X-API-Key") or (
        request.client.host if request.client else "unknown"
    )
    get_rate_limiter().check(api_key)


__all__ = [
    "RateLimitExceededError",
    "RateLimiter",
    "get_rate_limiter",
    "enforce_rate_limit",
]

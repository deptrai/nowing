"""Lightweight per-tool rate limiter for external HTTP APIs.

Each tool creates its own module-level `_ApiRateLimiter` instance.
The limiter uses a sliding-window (deque of call timestamps) to track
budget. When over budget, the caller is *delayed* (not rejected) until
the oldest timestamp falls outside the window.

Usage::

    _rl = _ApiRateLimiter(max_calls=100, window_seconds=60)

    async def my_tool_fn(...):
        await _rl.acquire()          # wait if over budget
        async with httpx.AsyncClient() as c:
            resp = await c.get(...)

This is intentionally separate from `_global_rate_bucket` in
chat_deepagent.py which gates LLM provider calls (Gemini/etc.).
"""

import asyncio
import collections
import logging
import time

logger = logging.getLogger(__name__)


class _ApiRateLimiter:
    """Sliding-window rate limiter for a single external API.

    Thread-safe via asyncio.Lock — safe for concurrent coroutines in
    a single event loop (the normal FastAPI / LangGraph deployment model).

    Args:
        max_calls: Maximum number of calls allowed within `window_seconds`.
        window_seconds: Width of the sliding window in seconds.
        name: Human-readable name for log messages.
    """

    def __init__(self, max_calls: int, window_seconds: float, name: str = "api") -> None:
        self._max_calls = max_calls
        self._window = window_seconds
        self._name = name
        self._timestamps: collections.deque[float] = collections.deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a call slot is available within the rate budget."""
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self._window

            # Evict expired timestamps
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= self._max_calls:
                # Sleep until the oldest call exits the window
                sleep_for = self._timestamps[0] - cutoff
                logger.debug(
                    "[%s] rate-limit: %d/%d calls in %.0fs window — sleeping %.2fs",
                    self._name,
                    len(self._timestamps),
                    self._max_calls,
                    self._window,
                    sleep_for,
                )
                await asyncio.sleep(sleep_for)
                # Re-evict after sleeping
                now = time.monotonic()
                cutoff = now - self._window
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()

            self._timestamps.append(time.monotonic())

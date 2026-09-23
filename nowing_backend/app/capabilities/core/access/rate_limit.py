"""Per-workspace rate limit for the capability doors (05).

A secondary abuse guard; the credit meter-gate (03c) is the primary control.
Fixed-window over Redis (shared across workers) with a per-worker in-memory
fallback when Redis is unavailable — mirroring the auth-endpoint limiter.

Assumptions & Trade-offs (Epic 9-3 BH-5):
- Primary security & abuse prevention is strictly enforced by the credit meter-gate (03c)
  and tenant authentication. Capability rate-limiting serves as secondary defense-in-depth.
- Under Redis outage, workers cannot coordinate state without adding heavy distributed consensus.
  To mitigate the N-worker rate multiplier (where N workers would otherwise permit N * 120 req/min),
  each worker's in-memory counter is scaled by CAPABILITY_RATE_LIMIT_FALLBACK_DIVISOR (default: 4,
  assuming ~4 workers per cluster). This limits each worker to ~30 req/min, keeping aggregate
  throughput bounded near the target limit of 120 req/min.
- Degraded mode logs a throttled warning so operations is alerted without log flooding.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

from app.config import config

logger = logging.getLogger(__name__)

CAPABILITY_RATE_LIMIT_PER_MINUTE = 120
CAPABILITY_RATE_LIMIT_FALLBACK_DIVISOR = 4
_WINDOW_SECONDS = 60
_KEY_PREFIX = "nowing:capability_rate_limit"

_redis = None
_memory: dict[str, list[float]] = defaultdict(list)
_memory_lock = Lock()
_last_fallback_log_ts: float = 0.0
_FALLBACK_LOG_INTERVAL_SEC: float = 30.0


def _log_fallback_warning(key: str, exc: Exception) -> None:
    """Log a throttled warning when entering in-memory fallback mode."""
    global _last_fallback_log_ts
    now = time.monotonic()
    if now - _last_fallback_log_ts >= _FALLBACK_LOG_INTERVAL_SEC:
        _last_fallback_log_ts = now
        logger.warning(
            "Capability rate limit: Redis unavailable (%s); falling back to per-worker "
            "in-memory counter (key=%s, fallback_divisor=%d). Rate limit is best-effort defense-in-depth.",
            exc,
            key,
            CAPABILITY_RATE_LIMIT_FALLBACK_DIVISOR,
        )


def _redis_client():
    global _redis
    if _redis is None:
        import redis

        _redis = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis


def _incr_memory(key: str, window_seconds: int) -> int:
    """Raw in-memory hit counter for the current worker."""
    now = time.monotonic()
    with _memory_lock:
        hits = [t for t in _memory[key] if now - t < window_seconds]
        hits.append(now)
        _memory[key] = hits
        return len(hits)


def _incr(key: str, window_seconds: int) -> int:
    """Increment the window counter for ``key`` and return the new count.

    When Redis is available, returns the global cluster count.
    When Redis is unavailable, falls back to the local in-memory counter scaled
    by ``CAPABILITY_RATE_LIMIT_FALLBACK_DIVISOR`` to prevent rate multiplication across workers.
    """
    try:
        client = _redis_client()
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window_seconds)
        return count
    except Exception as exc:  # redis rate limit error; fallback to in-memory rate limiting
        _log_fallback_warning(key, exc)
        raw_worker_count = _incr_memory(key, window_seconds)
        return raw_worker_count * CAPABILITY_RATE_LIMIT_FALLBACK_DIVISOR


async def _aincr(key: str, window_seconds: int) -> int:
    """Async-safe wrapper around the synchronous Redis-or-memory counter.

    The underlying Redis client (and the per-worker memory fallback lock) is
    synchronous, so the increment is off-loaded with :func:`asyncio.to_thread`.
    The sync :func:`_incr` is kept for callers that cannot await.
    """
    return await asyncio.to_thread(_incr, key, window_seconds)


async def enforce_capability_rate_limit(request: Request) -> None:
    """Cap requests per workspace per minute; raise 429 when exceeded."""
    workspace_id = request.path_params.get("workspace_id")
    count = await _aincr(f"{_KEY_PREFIX}:{workspace_id}", _WINDOW_SECONDS)
    if count > CAPABILITY_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this workspace. Try again shortly.",
        )

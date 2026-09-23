"""App rate_limiter helpers."""
import logging
import time
from collections import defaultdict
from threading import Lock

import redis
from fastapi import HTTPException, Request
from slowapi.util import get_remote_address  # noqa: F401 — kept for reference

from app.config import (
    config,
)
from app.observability import metrics as ot_metrics
from app.rate_limiter import get_real_client_ip

_error_logger = logging.getLogger("nowing.errors")

rate_limit_logger = logging.getLogger("nowing.rate_limit")


# ============================================================================
# Rate Limiting Configuration (SlowAPI + Redis)
# ============================================================================
# Uses the same Redis instance as Celery for zero additional infrastructure.
# Protects auth endpoints from brute force and user enumeration attacks.

# limiter is imported from app.rate_limiter (shared module to avoid circular imports)


# ============================================================================
# Auth-Specific Rate Limits (Redis-backed with in-memory fallback)
# ============================================================================
# Stricter per-IP limits on auth endpoints to prevent:
# - Brute force password attacks
# - User enumeration via REGISTER_USER_ALREADY_EXISTS
# - Email spam via forgot-password
#
# Primary: Redis INCR+EXPIRE (shared across all workers).
# Fallback: In-memory sliding window (per-worker) when Redis is unavailable.
# Same Redis instance as SlowAPI / Celery.
_rate_limit_redis: redis.Redis | None = None

# In-memory fallback rate limiter (per-worker, used only when Redis is down)
_memory_rate_limits: dict[str, list[float]] = defaultdict(list)
_memory_lock = Lock()


def _get_rate_limit_redis() -> redis.Redis:
    """Get or create Redis client for auth rate limiting."""
    global _rate_limit_redis
    if _rate_limit_redis is None:
        _rate_limit_redis = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _rate_limit_redis


def _check_rate_limit_memory(
    client_ip: str, max_requests: int, window_seconds: int, scope: str
):
    """
    In-memory fallback rate limiter using a sliding window.
    Used only when Redis is unavailable. Per-worker only (not shared),
    so effective limit = max_requests x num_workers.
    """
    key = f"{scope}:{client_ip}"
    now = time.monotonic()

    with _memory_lock:
        timestamps = [t for t in _memory_rate_limits[key] if now - t < window_seconds]

        if not timestamps:
            _memory_rate_limits.pop(key, None)
        else:
            _memory_rate_limits[key] = timestamps

        if len(timestamps) >= max_requests:
            rate_limit_logger.warning(
                f"Rate limit exceeded (in-memory fallback) on {scope} for IP {client_ip} "
                f"({len(timestamps)}/{max_requests} in {window_seconds}s)"
            )
            ot_metrics.record_rate_limit_rejection(scope=scope)
            raise HTTPException(
                status_code=429,
                detail="RATE_LIMIT_EXCEEDED",
            )

        _memory_rate_limits[key] = [*timestamps, now]


def _check_rate_limit(
    request: Request, max_requests: int, window_seconds: int, scope: str
):
    """
    Check per-IP rate limit using Redis. Raises 429 if exceeded.
    Uses atomic INCR + EXPIRE to avoid race conditions.
    Falls back to in-memory sliding window if Redis is unavailable.
    """
    client_ip = get_real_client_ip(request)
    key = f"nowing:auth_rate_limit:{scope}:{client_ip}"

    try:
        r = _get_rate_limit_redis()

        # Atomic: increment first, then set TTL if this is a new key
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        result = pipe.execute()
    except (redis.exceptions.RedisError, OSError) as exc:
        # Redis unavailable — fall back to in-memory rate limiting
        rate_limit_logger.warning(
            f"Redis unavailable for rate limiting ({scope}), "
            f"falling back to in-memory limiter for {client_ip}: {exc}"
        )
        _check_rate_limit_memory(client_ip, max_requests, window_seconds, scope)
        return

    current_count = result[0]  # INCR returns the new value

    if current_count > max_requests:
        rate_limit_logger.warning(
            f"Rate limit exceeded on {scope} for IP {client_ip} "
            f"({current_count}/{max_requests} in {window_seconds}s)"
        )
        ot_metrics.record_rate_limit_rejection(scope=scope)
        raise HTTPException(
            status_code=429,
            detail="RATE_LIMIT_EXCEEDED",
        )


def rate_limit_login(request: Request):
    """5 login attempts per minute per IP."""
    _check_rate_limit(request, max_requests=5, window_seconds=60, scope="login")


def rate_limit_register(request: Request):
    """3 registration attempts per minute per IP."""
    _check_rate_limit(request, max_requests=3, window_seconds=60, scope="register")


def rate_limit_password_reset(request: Request):
    """2 password reset attempts per minute per IP."""
    _check_rate_limit(
        request, max_requests=2, window_seconds=60, scope="password_reset"
    )


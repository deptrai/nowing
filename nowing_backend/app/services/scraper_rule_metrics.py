"""Lightweight per-platform scraper success/error metrics for INV-25.6.

Metrics are stored in Redis with a rolling TTL so the rate is a recent-window
approximation rather than a cumulative count. If Redis is unavailable the
functions fail silently; the scraper must not break because of metrics.
"""

from __future__ import annotations

import logging
from typing import Any

from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

_METRICS_WINDOW_SECONDS = 300
_SUCCESS_KEY = "scraper_rule:metrics:{platform}:success"
_ERROR_KEY = "scraper_rule:metrics:{platform}:error"


async def _redis() -> Any | None:
    try:
        return await get_redis_client()
    except Exception:
        logger.warning("Redis unavailable for scraper rule metrics")
        return None


async def record_success(platform: str) -> None:
    redis = await _redis()
    if redis is None:
        return
    try:
        await redis.incr(_SUCCESS_KEY.format(platform=platform.lower()))
        await redis.expire(
            _SUCCESS_KEY.format(platform=platform.lower()), _METRICS_WINDOW_SECONDS
        )
    except Exception:
        logger.exception("Failed to record scraper rule success metric")


async def record_failure(platform: str) -> None:
    redis = await _redis()
    if redis is None:
        return
    try:
        await redis.incr(_ERROR_KEY.format(platform=platform.lower()))
        await redis.expire(
            _ERROR_KEY.format(platform=platform.lower()), _METRICS_WINDOW_SECONDS
        )
    except Exception:
        logger.exception("Failed to record scraper rule error metric")


async def get_error_rate(platform: str) -> dict[str, Any]:
    """Return recent error rate percentage and call counts for a platform."""
    redis = await _redis()
    success_key = _SUCCESS_KEY.format(platform=platform.lower())
    error_key = _ERROR_KEY.format(platform=platform.lower())

    try:
        if redis is None:
            return {
                "platform": platform,
                "successes": 0,
                "errors": 0,
                "total": 0,
                "error_rate_pct": 0.0,
            }
        success, error = await redis.mget(success_key, error_key)
    except Exception:
        logger.exception("Failed to read scraper rule metrics")
        return {
            "platform": platform,
            "successes": 0,
            "errors": 0,
            "total": 0,
            "error_rate_pct": 0.0,
        }

    successes = int(success or 0)
    errors = int(error or 0)
    total = successes + errors
    error_rate_pct = (errors / total * 100) if total else 0.0
    return {
        "platform": platform,
        "successes": successes,
        "errors": errors,
        "total": total,
        "error_rate_pct": round(error_rate_pct, 2),
    }

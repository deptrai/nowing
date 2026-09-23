from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func

from app.celery_app import (
    CELERY_TASK_DEFAULT_QUEUE,
    CONNECTORS_QUEUE,
    LEAD_SCRAPERS_QUEUE,
)
from app.config import config
from app.db import (
    BillingEvent,
    CreditPurchase,
    TokenUsage,
)

logger = logging.getLogger(__name__)

_ALLOWED_PROVIDERS = {"openai", "anthropic", "google", "deepseek"}
_MAX_WINDOW_HOURS = 720  # 30 days
_CELERY_TASK_STALLED_SECONDS = getattr(config, "CELERY_TASK_STALLED_SECONDS", 300)
_QUEUE_NAMES = [
    CELERY_TASK_DEFAULT_QUEUE,
    CONNECTORS_QUEUE,
    LEAD_SCRAPERS_QUEUE,
    f"{CELERY_TASK_DEFAULT_QUEUE}.gateway",
]


def _redact_url(url: str | None) -> str | None:
    """Strip user:pass credentials from a proxy URL before returning it."""
    if not url:
        return url
    try:
        parsed = urlparse(url)
    except Exception:  # unparseable URL → return raw so caller still has something to display
        return url
    if not parsed.username and not parsed.password:
        return url
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return f"{parsed.scheme}://{netloc}{parsed.path or ''}"


def _redact_error(text: str | None) -> str | None:
    """Redact any embedded proxy credentials from an error string."""
    if not text:
        return text
    return re.sub(r"(https?://)[^:@\s]+:[^@\s]+@", r"\1***:***@", text)


def _is_redis_broker(url: str) -> bool:
    """Return True for Redis/Socket broker URLs used by Celery."""
    if not url:
        return False
    try:
        return urlparse(url).scheme in {"redis", "rediss", "unixsocket"}
    except Exception:  # unparseable URL → cheap prefix heuristic fallback
        return url.startswith(("redis://", "rediss://", "unixsocket://"))


def _clamp_window(window_hours: int) -> int:
    """Clamp requested window to [1, 720] hours."""
    if window_hours < 1:
        return 1
    if window_hours > _MAX_WINDOW_HOURS:
        return _MAX_WINDOW_HOURS
    return window_hours


def _make_time_bucket_expr(granularity: str) -> Any:
    """Return a SQLAlchemy expression that buckets created_at into a string period."""
    if granularity == "hour":
        return func.to_char(
            func.timezone("UTC", TokenUsage.created_at), "YYYY-MM-DD HH24:00"
        )
    if granularity == "day":
        return func.to_char(func.timezone("UTC", TokenUsage.created_at), "YYYY-MM-DD")
    return func.to_char(
        func.timezone("UTC", TokenUsage.created_at), "YYYY-MM-DD HH24:00"
    )


def _make_credit_bucket_expr(granularity: str) -> Any:
    """Return a SQLAlchemy expression that buckets CreditPurchase.completed_at (or created_at if pending) into a string period."""
    credit_ts = func.coalesce(CreditPurchase.completed_at, CreditPurchase.created_at)
    if granularity == "hour":
        return func.to_char(func.timezone("UTC", credit_ts), "YYYY-MM-DD HH24:00")
    if granularity == "day":
        return func.to_char(func.timezone("UTC", credit_ts), "YYYY-MM-DD")
    return func.to_char(func.timezone("UTC", credit_ts), "YYYY-MM-DD HH24:00")


def _make_billing_bucket_expr(granularity: str) -> Any:
    """Return a SQLAlchemy expression that buckets BillingEvent.created_at into a string period."""
    if granularity == "hour":
        return func.to_char(
            func.timezone("UTC", BillingEvent.created_at), "YYYY-MM-DD HH24:00"
        )
    if granularity == "day":
        return func.to_char(func.timezone("UTC", BillingEvent.created_at), "YYYY-MM-DD")
    return func.to_char(
        func.timezone("UTC", BillingEvent.created_at), "YYYY-MM-DD HH24:00"
    )


async def _maybe_async(value: Any) -> Any:
    """Unwrap a Celery promise/Result that may be awaitable."""
    if hasattr(value, "__await__"):
        return await value
    return value


async def _redis_queue_lengths(queue_names: list[str]) -> dict[str, int]:
    """Return the Redis list length for each Celery queue."""
    import redis.asyncio as aioredis

    broker_url = config.CELERY_BROKER_URL or ""
    if not _is_redis_broker(broker_url):
        return {}

    try:
        redis_client = aioredis.from_url(broker_url, socket_connect_timeout=2)
        lengths = {}
        for name in queue_names:
            try:
                lengths[name] = int(await redis_client.llen(name) or 0)
            except Exception:  # non-list key (e.g. discovered Redis string) → report 0
                # Non-list key (e.g. a discovered Redis string); report 0.
                lengths[name] = 0
    except Exception as exc:  # Redis unavailable → return empty lengths; telemetry degrades to zeros
        logger.warning("Redis queue length query failed: %s", exc)
        lengths = {}
    finally:
        if "redis_client" in locals():
            await redis_client.aclose()

    return lengths


async def _redis_queue_stalled_and_throughput(
    queue_names: list[str],
) -> dict[str, tuple[int, int]]:
    """Compute stalled count and throughput_per_min for Redis-backed queues.

    Stalled = messages whose ``timestamps.sent`` or ``nowing.enqueued_at_ns``
    is older than ``_CELERY_TASK_STALLED_SECONDS``. Throughput is estimated from
    messages enqueued within the last 60 seconds.
    """
    import redis.asyncio as aioredis

    broker_url = config.CELERY_BROKER_URL or ""
    if not _is_redis_broker(broker_url):
        return {}

    now_wall = time.time()
    now_mono = time.monotonic_ns()
    threshold = _CELERY_TASK_STALLED_SECONDS

    results: dict[str, tuple[int, int]] = {}
    redis_client = None
    try:
        redis_client = aioredis.from_url(broker_url, socket_connect_timeout=2)
        for name in queue_names:
            try:
                queue_len = int(await redis_client.llen(name) or 0)
            except Exception:  # non-list key → report 0 length
                queue_len = 0

            stalled = 0
            recent = 0
            if queue_len > 0:
                try:
                    sample_size = min(queue_len, 500)
                    messages = await redis_client.lrange(name, 0, sample_size - 1)
                    for raw in messages:
                        try:
                            payload = json.loads(raw)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            stalled += 1
                            continue

                        timestamps = (
                            payload.get("properties", {}).get("timestamps", {}) or {}
                        )
                        sent_at = timestamps.get("sent")
                        enqueued_ns = payload.get("headers", {}).get(
                            "nowing.enqueued_at_ns"
                        )

                        if sent_at is not None:
                            try:
                                age = now_wall - float(sent_at)
                                if age > threshold:
                                    stalled += 1
                                elif age <= 60:
                                    recent += 1
                            except (ValueError, TypeError) as exc:
                                logger.debug("Suppressed %r", exc)
                        elif enqueued_ns is not None:
                            try:
                                age_s = (now_mono - int(enqueued_ns)) / 1e9
                                if age_s > threshold:
                                    stalled += 1
                                elif age_s <= 60:
                                    recent += 1
                            except (ValueError, TypeError) as exc:
                                logger.debug("Suppressed %r", exc)

                    if sample_size < queue_len and sample_size > 0:
                        stalled = int(stalled * (queue_len / sample_size))
                except Exception as exc:  # per-queue stalled computation failure → report zeros for that queue
                    logger.warning(
                        "Error computing stalled stats for %s: %s", name, exc
                    )

            results[name] = (stalled, recent)
    except Exception as exc:  # Redis unavailable → return empty stalled stats; telemetry degrades to zeros
        logger.warning("Redis queue stalled query failed: %s", exc)
    finally:
        if redis_client is not None:
            await redis_client.aclose()

    return results

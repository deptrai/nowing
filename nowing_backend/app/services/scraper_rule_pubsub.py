from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.services import scraper_rule_cache as _rule_cache_module


def get_rule_cache() -> Any:
    return _rule_cache_module


invalidate_rule_cache = _rule_cache_module.invalidate

logger = logging.getLogger(__name__)

SUBSCRIBER_TASKS: set[asyncio.Task] = set()
SUBSCRIPTION_CHANNEL = "scraper_config_updated"


async def publish_rule_update(
    redis: Any,
    platform: str,
    version: int,
    is_active: bool,
    circuit_breaker_tripped: bool,
    updated_at: str | None = None,
) -> None:
    """Publish a JSON notification that a scraper rule changed.

    Payload shape aligns with AC-5:
    ``{"platform", "version", "is_active", "updated_at"}``,
    plus ``circuit_breaker_tripped`` for worker-side breaker checks.
    """
    payload = json.dumps(
        {
            "platform": platform,
            "version": version,
            "is_active": is_active,
            "updated_at": updated_at,
            "circuit_breaker_tripped": circuit_breaker_tripped,
        },
        default=str,
    )
    if redis is None:
        return
    try:
        await redis.publish(SUBSCRIPTION_CHANNEL, payload)
    except Exception:
        logger.exception("Failed to publish scraper rule update")


async def start_rule_subscriber(
    redis: Any,
    callback: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    """Subscribe to scraper config updates and invalidate the local cache."""
    try:
        pubsub = redis.pubsub()
    except AttributeError:
        logger.warning("Redis client does not support pubsub")
        return

    try:
        await pubsub.subscribe(SUBSCRIPTION_CHANNEL)
    except Exception:
        logger.exception("Failed to subscribe to scraper config updates")
        return

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if not message or message.get("type") != "message":
                continue

            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

            platform = data.get("platform")
            if not platform:
                continue

            get_rule_cache().invalidate(platform)

            if callback is not None:
                await callback(platform)
    except asyncio.CancelledError:
        await pubsub.unsubscribe(SUBSCRIPTION_CHANNEL)
        raise


def start_background_subscriber(redis: Any) -> asyncio.Task:
    """Start a background subscriber task and keep a hard reference."""
    task = asyncio.create_task(start_rule_subscriber(redis))
    SUBSCRIBER_TASKS.add(task)
    task.add_done_callback(SUBSCRIBER_TASKS.discard)
    return task

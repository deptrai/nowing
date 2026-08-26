"""Red-phase unit tests for Story 25.5 — scraper rule Pub/Sub and cache.

These tests encode the expected contract and will fail until
`app/services/scraper_rule_pubsub.py` and `app/services/scraper_rule_cache.py`
are implemented.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.unit]


def _load_pubsub() -> Any:
    try:
        return importlib.import_module("app.services.scraper_rule_pubsub")
    except ModuleNotFoundError as exc:
        pytest.fail(f"not implemented: {exc}")


def _load_cache() -> Any:
    try:
        return importlib.import_module("app.services.scraper_rule_cache")
    except ModuleNotFoundError as exc:
        pytest.fail(f"not implemented: {exc}")


class TestScraperRulePubSub:
    """AC-5: Redis Pub/Sub live invalidation."""

    async def test_publish_rule_update_posts_to_scraper_config_updated(self) -> None:
        mod = _load_pubsub()
        redis = AsyncMock()

        await mod.publish_rule_update(
            redis=redis,
            platform="batdongsan",
            version=7,
            is_active=True,
            circuit_breaker_tripped=False,
        )

        redis.publish.assert_awaited_once()
        args, _ = redis.publish.call_args
        assert args[0] == "scraper_config_updated"
        payload = args[1]
        assert '"platform": "batdongsan"' in payload
        assert '"version": 7' in payload

    async def test_subscriber_invalidate_rule_cache_on_message(self) -> None:
        mod = _load_pubsub()
        cache = _load_cache()
        cache.set("batdongsan", {"version": 6})

        callback_called = False

        async def callback(platform: str) -> None:
            nonlocal callback_called
            callback_called = True
            assert platform == "batdongsan"

        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "app.services.scraper_rule_pubsub.get_rule_cache",
                lambda: cache,
            )
            await mod.start_rule_subscriber(
                redis=AsyncMock(),
                callback=callback,
            )

        assert callback_called

    async def test_invalidate_rule_cache_clears_entry(self) -> None:
        cache = _load_cache()
        cache.set("batdongsan", {"version": 6})

        mod = _load_pubsub()
        mod.invalidate_rule_cache("batdongsan")

        assert cache.get("batdongsan") is None

    async def test_publish_handles_redis_connection_error(self) -> None:
        mod = _load_pubsub()
        redis = AsyncMock()
        redis.publish.side_effect = ConnectionError("redis down")

        # Should not raise — log warning and continue.
        await mod.publish_rule_update(
            redis=redis,
            platform="batdongsan",
            version=7,
            is_active=True,
            circuit_breaker_tripped=False,
        )


class TestScraperRuleCache:
    """AC-5 / AC-6: TTL in-memory cache fallback."""

    def test_cache_get_returns_none_for_unknown_platform(self) -> None:
        cache = _load_cache()
        assert cache.get("unknown_platform") is None

    def test_cache_set_with_ttl(self) -> None:
        cache = _load_cache()
        cache.set("batdongsan", {"version": 7}, ttl_seconds=5)
        assert cache.get("batdongsan") == {"version": 7}

    def test_cache_expires_after_ttl(self) -> None:
        cache = _load_cache()
        cache.set("batdongsan", {"version": 7}, ttl_seconds=0.01)
        import time

        time.sleep(0.02)
        assert cache.get("batdongsan") is None

    def test_cache_ttl_default_is_5_seconds(self) -> None:
        mod = _load_cache()
        assert mod.DEFAULT_TTL_SECONDS == 5

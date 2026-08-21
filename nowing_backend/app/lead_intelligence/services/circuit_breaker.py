"""Scraper Platform Circuit Breaker (Story 23.1 / AC-3 & INV-23.3).

Governed by:
- AC-3: 3 Consecutive 429/CAPTCHA Anti-Bot Blocks Trip Circuit for 10 Minutes
- INV-23.3: Circuit Breaker Persistence in Redis (circuit_breaker:scraper:{platform}, TTL 600s)
- Architecture Spine: architecture-epic23-lead-infrastructure.md
"""

from __future__ import annotations

import logging
from typing import Any

from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

CIRCUIT_FAILURE_THRESHOLD: int = 3
CIRCUIT_COOLDOWN_SECONDS: int = 600  # 10 minutes (INV-23.3)


class PlatformCircuitBreaker:
    """Per-platform circuit breaker tripping after 3 consecutive anti-bot blocks."""

    def __init__(
        self,
        redis_client: Any = None,
        failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
        cooldown_seconds: int = CIRCUIT_COOLDOWN_SECONDS,
    ) -> None:
        self._redis = redis_client
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

    async def _get_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        return await get_redis_client()

    def _state_key(self, platform: str) -> str:
        return f"circuit_breaker:scraper:{platform.strip().lower()}"

    def _failure_counter_key(self, platform: str) -> str:
        return f"circuit_breaker:failures:{platform.strip().lower()}"

    async def is_available(self, platform: str) -> bool:
        """Check if scraper platform circuit is CLOSED (available) with graceful fail-open."""
        try:
            redis = await self._get_redis()
            state_key = self._state_key(platform)
            val = await redis.get(state_key)
            if val is None:
                return True
            if isinstance(val, bytes):
                val = val.decode("utf-8")
            return val != "OPEN"
        except Exception as exc:
            logger.warning(
                "Circuit breaker check failed for %s: %s (failing open)",
                platform,
                exc,
            )
            return True

    async def record_failure(
        self,
        platform: str,
        reason: str,
        status_code: int | None = None,
    ) -> bool:
        """
        Record a scraping failure (429 / CAPTCHA / anti-bot block).
        Returns True if circuit tripped to OPEN, False otherwise.
        """
        try:
            redis = await self._get_redis()
            normalized_platform = platform.strip().lower()
            counter_key = self._failure_counter_key(normalized_platform)

            streak = int(await redis.incr(counter_key))
            await redis.expire(counter_key, self.cooldown_seconds)

            logger.warning(
                "Scraper platform %s recorded failure (%s, code=%s) streak=%d/%d",
                normalized_platform,
                reason,
                status_code,
                streak,
                self.failure_threshold,
            )

            if streak >= self.failure_threshold:
                state_key = self._state_key(normalized_platform)
                await redis.set(state_key, "OPEN", ex=self.cooldown_seconds)
                logger.error(
                    "CIRCUIT BREAKER TRIPPED for %s: cooldown for %ds (INV-23.3)",
                    normalized_platform,
                    self.cooldown_seconds,
                )
                return True

            return False
        except Exception as exc:
            logger.error(
                "Failed to record circuit breaker failure for %s: %s", platform, exc
            )
            return False

    async def record_success(self, platform: str) -> None:
        """Reset failure streak and clear OPEN state on successful scrape."""
        try:
            redis = await self._get_redis()
            normalized_platform = platform.strip().lower()
            await redis.delete(self._failure_counter_key(normalized_platform))
        except Exception as exc:
            logger.warning("Failed to reset circuit breaker for %s: %s", platform, exc)

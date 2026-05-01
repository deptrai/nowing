import logging
import time
from typing import Literal

from app.config import config
from app.services.crypto_cache_lock import get_redis_client

logger = logging.getLogger(__name__)

# Constants for Breaker behavior
FAILURE_THRESHOLD = 5
FAILURE_WINDOW_SECONDS = 60
OPEN_COOLDOWN_SECONDS = 30

CircuitState = Literal["closed", "open", "half_open"]


class RedisCircuitBreaker:
    """Global circuit breaker using Redis for shared state across workers.

    Pattern:
    - Track consecutive failures per source.
    - If threshold reached, state -> OPEN for COOLDOWN seconds.
    - After COOLDOWN, state -> HALF_OPEN (allow 1 probe).
    """

    def __init__(self):
        self._redis = get_redis_client()
        self._prefix = "cb:"

    def _get_keys(self, source: str):
        return {
            "fail_count": f"{self._prefix}fail_count:{source}",
            "open_until": f"{self._prefix}open_until:{source}",
        }

    async def is_open(self, source: str) -> bool:
        """Check if circuit is open. If Redis is down, defaults to False (closed)."""
        if self._redis is None:
            return False  # Graceful degradation: allow calls if Redis is down

        keys = self._get_keys(source)
        try:
            open_until_str = await self._redis.get(keys["open_until"])
            if not open_until_str:
                return False

            open_until = float(open_until_str)
            if time.time() < open_until:
                return True

            # Cooldown expired -> Half-open (effectively closed but next failure re-opens immediately)
            return False
        except Exception as exc:
            logger.warning("RedisCircuitBreaker.is_open failed for %s: %s", source, exc)
            return False

    async def record_failure(self, source: str):
        """Increment failure count and open circuit if threshold reached."""
        if self._redis is None:
            return

        keys = self._get_keys(source)
        try:
            # Increment failure count within the window
            count = await self._redis.incr(keys["fail_count"])
            if count == 1:
                await self._redis.expire(keys["fail_count"], FAILURE_WINDOW_SECONDS)

            if count >= FAILURE_THRESHOLD:
                # Open the circuit
                open_until = time.time() + OPEN_COOLDOWN_SECONDS
                await self._redis.set(keys["open_until"], str(open_until), ex=OPEN_COOLDOWN_SECONDS)
                logger.warning(
                    "Circuit breaker OPENED for %s after %d failures. Paused for %ds",
                    source, count, OPEN_COOLDOWN_SECONDS
                )
        except Exception as exc:
            logger.warning("RedisCircuitBreaker.record_failure failed for %s: %s", source, exc)

    async def record_success(self, source: str):
        """Reset failure count and close circuit."""
        if self._redis is None:
            return

        keys = self._get_keys(source)
        try:
            await self._redis.delete(keys["fail_count"], keys["open_until"])
        except Exception as exc:
            logger.warning("RedisCircuitBreaker.record_success failed for %s: %s", source, exc)


# Global singleton instance
circuit_breaker = RedisCircuitBreaker()

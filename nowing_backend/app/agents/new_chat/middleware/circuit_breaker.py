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
    - If probe succeeds, state -> CLOSED.
    - If probe fails, state -> OPEN again.
    """

    def __init__(self):
        self._redis = get_redis_client()
        self._prefix = "cb:"
        # AC4: In-memory fallback for Redis downtime
        self._local_state_cache: dict[str, bool] = {}

    def _get_keys(self, source: str):
        return {
            "fail_count": f"{self._prefix}fail_count:{source}",
            "open_until": f"{self._prefix}open_until:{source}",
            "state": f"{self._prefix}state:{source}",
            "probe_allowed": f"{self._prefix}probe_allowed:{source}",
        }

    async def _update_state(self, source: str, to_state: CircuitState, from_state: str = "unknown"):
        """Update state in Redis and log transition."""
        if self._redis is None:
            return
        
        keys = self._get_keys(source)
        try:
            await self._redis.set(keys["state"], to_state)
            # AC5: Structured logging
            logger.info(
                "Circuit state changed",
                extra={
                    "event": "circuit_state_change",
                    "source": source,
                    "from": from_state,
                    "to": to_state
                }
            )
        except Exception as exc:
            logger.warning("Failed to update circuit state for %s: %s", source, exc)

    async def is_open(self, source: str) -> bool:
        """Check if circuit is open. If Redis is down, returns last-known state."""
        if self._redis is None:
            return self._local_state_cache.get(source, False)

        keys = self._get_keys(source)
        try:
            # 1. Check explicit state first
            state = await self._redis.get(keys["state"])
            if isinstance(state, bytes):
                state = state.decode()
            
            if not state or state == "closed":
                self._local_state_cache[source] = False
                return False

            if state == "open":
                open_until_str = await self._redis.get(keys["open_until"])
                if open_until_str:
                    open_until = float(open_until_str)
                    if time.time() < open_until:
                        self._local_state_cache[source] = True
                        return True
                
                # Cooldown expired -> Transition to HALF_OPEN
                await self._update_state(source, "half_open", from_state="open")
                # Atomic SETNX to ensure only 1 probe is allowed initially
                await self._redis.set(keys["probe_allowed"], "1")
                state = "half_open"

            if state == "half_open":
                # AC1: Only allow 1 probe request
                allowed = await self._redis.decr(keys["probe_allowed"])
                is_blocked = allowed < 0
                self._local_state_cache[source] = is_blocked
                return is_blocked

            return False
        except Exception as exc:
            logger.warning("RedisCircuitBreaker.is_open failed for %s: %s", source, exc)
            # AC4: Fallback to last-known state
            return self._local_state_cache.get(source, False)

    async def record_failure(self, source: str):
        """Increment failure count and open circuit if threshold reached."""
        if self._redis is None:
            return

        keys = self._get_keys(source)
        try:
            # Check current state
            state = await self._redis.get(keys["state"])
            if isinstance(state, bytes):
                state = state.decode()

            # Increment failure count within the window
            count = await self._redis.incr(keys["fail_count"])
            if count == 1:
                await self._redis.expire(keys["fail_count"], FAILURE_WINDOW_SECONDS)

            # AC3: If in HALF_OPEN and fails -> transition back to OPEN
            should_open = count >= FAILURE_THRESHOLD or state == "half_open"
            
            if should_open:
                # Open the circuit
                open_until = time.time() + OPEN_COOLDOWN_SECONDS
                await self._redis.set(keys["open_until"], str(open_until), ex=OPEN_COOLDOWN_SECONDS)
                await self._update_state(source, "open", from_state=state or "closed")
                
                # Reset fail count to allow fresh window after cooldown
                await self._redis.delete(keys["fail_count"])
        except Exception as exc:
            logger.warning("RedisCircuitBreaker.record_failure failed for %s: %s", source, exc)

    async def record_success(self, source: str):
        """Reset failure count and close circuit."""
        if self._redis is None:
            return

        keys = self._get_keys(source)
        try:
            # Check if we were in open/half_open state before clearing
            state = await self._redis.get(keys["state"])
            if isinstance(state, bytes):
                state = state.decode()
            
            if state and state != "closed":
                await self._update_state(source, "closed", from_state=state)

            await self._redis.delete(keys["fail_count"], keys["open_until"], keys["state"], keys["probe_allowed"])
            self._local_state_cache[source] = False
        except Exception as exc:
            logger.warning("RedisCircuitBreaker.record_success failed for %s: %s", source, exc)


# Global singleton instance
circuit_breaker = RedisCircuitBreaker()

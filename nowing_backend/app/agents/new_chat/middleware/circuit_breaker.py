import json
import logging
import time
from typing import Literal

from app.config import config  # noqa: F401  (kept for downstream import compat)
from app.services.crypto_cache_lock import get_redis_client

logger = logging.getLogger(__name__)

# Constants for Breaker behavior — per Story 10.1.1 AC3:
# "Nansen API trả ≥3 lỗi 5xx liên tiếp trong 60s" → threshold=3, window=60s, cooldown=30s
FAILURE_THRESHOLD = 3
FAILURE_WINDOW_SECONDS = 60
OPEN_COOLDOWN_SECONDS = 30
# Probe allowance is bound to the cooldown window — if no probe arrives within
# OPEN_COOLDOWN_SECONDS, the next is_open() call will re-enter the expired
# branch and re-create a fresh probe slot via SET NX. This prevents stale
# negative `probe_allowed` values from blocking the circuit forever.
PROBE_ALLOWED_TTL_SECONDS = OPEN_COOLDOWN_SECONDS
# State key TTL guards against orphaned state if record_success/record_failure
# never fires. Set generously so legitimate long-open windows are unaffected.
STATE_KEY_TTL_SECONDS = OPEN_COOLDOWN_SECONDS * 4

CircuitState = Literal["closed", "open", "half_open"]


def _emit_state_change_log(source: str, from_state: str, to_state: str) -> None:
    """Emit a single JSON-formatted log line for circuit state transitions.

    AC#5 requires structured JSON regardless of upstream logging config, so we
    serialise inline rather than relying on `extra=` + a JSON formatter.

    `source` is vendor-scoped (e.g. "nansen") — multiple tools sharing the same
    upstream API share one breaker because they share rate limits and outage
    modes. Per-tool granularity would slow detection (3x failures needed) and
    add no recovery benefit.
    """
    logger.info(
        json.dumps(
            {
                "event": "circuit_state_change",
                "source": source,
                "from": from_state,
                "to": to_state,
            }
        )
    )


class RedisCircuitBreaker:
    """Global circuit breaker using Redis for shared state across workers.

    Pattern:
    - Track consecutive failures per source.
    - If threshold reached, state -> OPEN for COOLDOWN seconds.
    - After COOLDOWN, state -> HALF_OPEN (allow 1 probe via atomic SETNX).
    - If probe succeeds, state -> CLOSED.
    - If probe fails, state -> OPEN again.
    """

    def __init__(self):
        self._redis = get_redis_client()
        self._prefix = "cb:"
        # AC4: In-memory fallback for Redis downtime — mirrors is_open() result.
        self._local_state_cache: dict[str, bool] = {}

    def _get_keys(self, source: str):
        return {
            "fail_count": f"{self._prefix}fail_count:{source}",
            "open_until": f"{self._prefix}open_until:{source}",
            "state": f"{self._prefix}state:{source}",
            "probe_allowed": f"{self._prefix}probe_allowed:{source}",
        }

    async def _update_state(
        self, source: str, to_state: CircuitState, from_state: str = "unknown"
    ):
        """Persist state to Redis with TTL and log structured transition."""
        if self._redis is None:
            return

        keys = self._get_keys(source)
        try:
            await self._redis.set(keys["state"], to_state, ex=STATE_KEY_TTL_SECONDS)
            _emit_state_change_log(source, from_state, to_state)
        except Exception as exc:
            logger.warning("Failed to update circuit state for %s: %s", source, exc)

    async def is_open(self, source: str) -> bool:
        """Check if circuit is open. If Redis is down, returns last-known state."""
        if self._redis is None:
            return self._local_state_cache.get(source, False)

        keys = self._get_keys(source)
        try:
            state = await self._redis.get(keys["state"])
            if isinstance(state, bytes):
                state = state.decode()

            if not state or state == "closed":
                self._local_state_cache[source] = False
                return False

            if state == "open":
                open_until_str = await self._redis.get(keys["open_until"])
                if open_until_str is not None:
                    if isinstance(open_until_str, bytes):
                        open_until_str = open_until_str.decode()
                    try:
                        open_until = float(open_until_str)
                    except (TypeError, ValueError):
                        open_until = 0.0
                    if time.time() < open_until:
                        self._local_state_cache[source] = True
                        return True

                # Cooldown expired -> Transition to HALF_OPEN.
                # SET NX is atomic across workers: only one worker successfully
                # creates the probe_allowed slot; concurrent workers' SET NX is
                # a no-op and they will see allowed<0 after DECR.
                created = await self._redis.set(
                    keys["probe_allowed"],
                    "1",
                    nx=True,
                    ex=PROBE_ALLOWED_TTL_SECONDS,
                )
                if created:
                    await self._update_state(source, "half_open", from_state="open")
                state = "half_open"

            if state == "half_open":
                # AC1: Only allow 1 probe request — DECR is atomic.
                allowed = await self._redis.decr(keys["probe_allowed"])
                is_blocked = allowed < 0
                self._local_state_cache[source] = is_blocked
                return is_blocked

            return False
        except Exception as exc:
            logger.warning("RedisCircuitBreaker.is_open failed for %s: %s", source, exc)
            # AC4: Fallback to last-known state on Redis exception.
            return self._local_state_cache.get(source, False)

    async def record_failure(self, source: str):
        """Increment failure count and open circuit if threshold reached."""
        if self._redis is None:
            return

        keys = self._get_keys(source)
        try:
            state = await self._redis.get(keys["state"])
            if isinstance(state, bytes):
                state = state.decode()

            # If circuit is already OPEN with a live cooldown, no work to do.
            # This avoids a race where worker A is opening the circuit while
            # worker B's record_failure also tries to re-open with a fresh
            # cooldown, churning open_until repeatedly.
            if state == "open":
                return

            count = await self._redis.incr(keys["fail_count"])
            if count == 1:
                await self._redis.expire(keys["fail_count"], FAILURE_WINDOW_SECONDS)

            # AC3: A failure during HALF_OPEN reopens the circuit immediately.
            should_open = count >= FAILURE_THRESHOLD or state == "half_open"

            if should_open:
                open_until = time.time() + OPEN_COOLDOWN_SECONDS
                await self._redis.set(
                    keys["open_until"], str(open_until), ex=OPEN_COOLDOWN_SECONDS
                )
                await self._update_state(source, "open", from_state=state or "closed")

                # Reset fail count + clear stale probe slot so the next HALF_OPEN
                # transition starts from a clean state.
                await self._redis.delete(keys["fail_count"], keys["probe_allowed"])
                self._local_state_cache[source] = True
        except Exception as exc:
            logger.warning("RedisCircuitBreaker.record_failure failed for %s: %s", source, exc)

    async def record_success(self, source: str):
        """Reset failure count and close circuit."""
        if self._redis is None:
            return

        keys = self._get_keys(source)
        try:
            state = await self._redis.get(keys["state"])
            if isinstance(state, bytes):
                state = state.decode()

            if state and state != "closed":
                await self._update_state(source, "closed", from_state=state)

            await self._redis.delete(
                keys["fail_count"], keys["open_until"], keys["state"], keys["probe_allowed"]
            )
            self._local_state_cache[source] = False
        except Exception as exc:
            logger.warning("RedisCircuitBreaker.record_success failed for %s: %s", source, exc)


# Global singleton instance
circuit_breaker = RedisCircuitBreaker()

"""Circuit Breaker for XActions MCP calls (Story 40.1).

Implements a circuit breaker pattern to fail-fast when XActions
is experiencing issues, preventing worker hang and resource exhaustion.

States:
    CLOSED: Normal operation, requests pass through
    OPEN: After `failure_threshold` consecutive failures, requests fail fast for `recovery_timeout` seconds
    HALF_OPEN: After timeout, allow one probe request to test recovery
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Callable, TypeVar

import anyio
import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerStats:
    """Snapshot of circuit breaker statistics."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    opened_at: float = 0.0


class CircuitBreakerOpenError(RuntimeError):
    """Raised when circuit breaker is OPEN and request should fail fast."""

    def __init__(self, message: str = "Circuit breaker is OPEN"):
        super().__init__(message)
        self.message = message


class XActionsCircuitBreaker:
    """Circuit breaker for XActions MCP calls.

    Configuration:
        failure_threshold: Consecutive failures before opening (default: 3)
        recovery_timeout: Seconds to wait before attempting half-open (default: 60)
        expected_exceptions: Exception types that count as failures
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        expected_exceptions: tuple[type[Exception], ...] = (
            ConnectionError,
            asyncio.TimeoutError,
            TimeoutError,
            anyio.ClosedResourceError,
            anyio.BrokenResourceError,
            anyio.EndOfStream,
            httpx.TransportError,
        ),
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        self._stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        # Story 40.1: serializes the single probe call in HALF_OPEN
        self._probe_in_flight: bool = False

    @property
    def stats(self) -> CircuitBreakerStats:
        """Return an immutable snapshot of current stats."""
        return replace(self._stats)

    @property
    def is_closed(self) -> bool:
        return self._stats.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self._stats.state == CircuitState.OPEN

    async def reset(self) -> None:
        """Reset the circuit breaker to CLOSED (test/admin use)."""
        async with self._lock:
            self._stats = CircuitBreakerStats()
            self._probe_in_flight = False

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self._stats.state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._stats.opened_at
                if elapsed < self.recovery_timeout:
                    remaining = self.recovery_timeout - elapsed
                    raise CircuitBreakerOpenError(
                        f"XActions circuit breaker is OPEN - "
                        f"retry in {remaining:.1f}s"
                    )
                # Transition to half-open: only the first caller probes
                self._stats.state = CircuitState.HALF_OPEN
                self._stats.failure_count = 0  # fresh probe attempt
                self._probe_in_flight = True
                logger.info("XActions circuit breaker: HALF_OPEN (testing recovery)")

            elif self._stats.state == CircuitState.HALF_OPEN:
                # Only one probe allowed; others fail fast
                if self._probe_in_flight:
                    raise CircuitBreakerOpenError(
                        "XActions circuit breaker is HALF_OPEN - probe in flight"
                    )
                self._probe_in_flight = True

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exceptions:
            await self._on_failure()
            raise
        # Non-expected exceptions propagate without tripping the breaker
        # (they're programming errors, not service failures)

    async def _on_success(self) -> None:
        async with self._lock:
            self._stats.state = CircuitState.CLOSED
            self._stats.failure_count = 0
            self._stats.last_success_time = time.monotonic()
            self._probe_in_flight = False
            logger.debug("XActions circuit breaker: CLOSED (success)")

    async def _on_failure(self) -> None:
        async with self._lock:
            self._stats.failure_count += 1
            self._stats.last_failure_time = time.monotonic()
            self._probe_in_flight = False

            if self._stats.state == CircuitState.HALF_OPEN:
                # Probe failed → back to OPEN
                self._stats.state = CircuitState.OPEN
                self._stats.opened_at = time.monotonic()
                logger.warning(
                    "XActions circuit breaker: OPEN (half-open probe failed)"
                )
            elif self._stats.failure_count >= self.failure_threshold:
                self._stats.state = CircuitState.OPEN
                self._stats.opened_at = time.monotonic()
                logger.warning(
                    "XActions circuit breaker: OPEN "
                    f"(failures={self._stats.failure_count}, "
                    f"recovery in {self.recovery_timeout}s)"
                )


# Global circuit breaker instance shared by all MCP calls
XACTIONS_CIRCUIT_BREAKER = XActionsCircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60.0,
    expected_exceptions=(
        ConnectionError,
        asyncio.TimeoutError,
        TimeoutError,
        anyio.ClosedResourceError,
        anyio.BrokenResourceError,
        anyio.EndOfStream,
        httpx.TransportError,
    ),
)

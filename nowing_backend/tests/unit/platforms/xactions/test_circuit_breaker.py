"""Unit tests for XActions Circuit Breaker (Story 40.1)."""

import asyncio
import pytest

from app.proprietary.platforms.xactions.circuit_breaker import (
    XActionsCircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
)


class TestXActionsCircuitBreaker:
    """Test suite for XActionsCircuitBreaker."""

    @pytest.fixture
    def breaker(self):
        """Create a fresh circuit breaker for each test."""
        return XActionsCircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
            expected_exceptions=(ConnectionError, asyncio.TimeoutError),
        )

    @pytest.mark.asyncio
    async def test_circuit_closed_initially(self, breaker):
        """Test that circuit starts in CLOSED state."""
        assert breaker.is_closed
        assert not breaker.is_open
        assert breaker.stats.state == CircuitState.CLOSED
        assert breaker.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_successful_call(self, breaker):
        """Test that successful calls pass through."""
        async def success_func():
            return {"success": True}

        result = await breaker.call(success_func)
        assert result == {"success": True}
        assert breaker.is_closed
        assert breaker.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_single_failure_doesnt_open(self, breaker):
        """Test that single failure doesn't open circuit."""
        async def fail_func():
            raise ConnectionError("Connection failed")

        with pytest.raises(ConnectionError):
            await breaker.call(fail_func)

        assert breaker.is_closed
        assert breaker.stats.failure_count == 1

    @pytest.mark.asyncio
    async def test_threshold_failures_opens_circuit(self, breaker):
        """Test that reaching failure threshold opens circuit."""
        async def fail_func():
            raise ConnectionError("Connection failed")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(fail_func)

        assert breaker.is_open
        assert breaker.stats.state == CircuitState.OPEN
        assert breaker.stats.failure_count == 3

    @pytest.mark.asyncio
    async def test_circuit_open_fails_fast(self, breaker):
        """Test that open circuit raises CircuitBreakerOpenError."""
        async def fail_func():
            raise ConnectionError("Connection failed")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(fail_func)

        async def never_called():
            pytest.fail("Should not be called when circuit is open")

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await breaker.call(never_called)

        assert "OPEN" in str(exc_info.value)
        # Retry-in hint present
        assert "retry in" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        fast_breaker = XActionsCircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms for testing
            expected_exceptions=(ConnectionError,),
        )

        async def fail_func():
            raise ConnectionError("Connection failed")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await fast_breaker.call(fail_func)

        assert fast_breaker.is_open

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        async def success_func():
            return {"success": True}

        result = await fast_breaker.call(success_func)
        assert result == {"success": True}
        assert fast_breaker.is_closed

    @pytest.mark.asyncio
    async def test_half_open_failure_returns_to_open(self):
        """Test that failure in HALF_OPEN returns to OPEN."""
        fast_breaker = XActionsCircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,
            expected_exceptions=(ConnectionError,),
        )

        async def fail_func():
            raise ConnectionError("Connection failed")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await fast_breaker.call(fail_func)

        await asyncio.sleep(0.15)

        with pytest.raises(ConnectionError):
            await fast_breaker.call(fail_func)

        assert fast_breaker.is_open

    @pytest.mark.asyncio
    async def test_half_open_single_probe_only(self):
        """Test that only one probe call is allowed in HALF_OPEN."""
        fast_breaker = XActionsCircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.05,
            expected_exceptions=(ConnectionError,),
        )

        async def fail_func():
            raise ConnectionError("fail")

        # Open circuit
        with pytest.raises(ConnectionError):
            await fast_breaker.call(fail_func)

        # Wait for recovery timeout
        await asyncio.sleep(0.1)

        # First probe call enters HALF_OPEN
        probe_started = asyncio.Event()
        probe_done = asyncio.Event()

        async def slow_probe():
            probe_started.set()
            await probe_done.wait()
            return "ok"

        # Start probe in background
        probe_task = asyncio.create_task(fast_breaker.call(slow_probe))
        await probe_started.wait()

        # Second concurrent call should fail fast (probe in flight)
        async def concurrent():
            return "should not reach"

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await fast_breaker.call(concurrent)

        assert "HALF_OPEN" in str(exc_info.value)

        # Let probe finish
        probe_done.set()
        result = await probe_task
        assert result == "ok"
        assert fast_breaker.is_closed

    @pytest.mark.asyncio
    async def test_non_expected_exception_does_not_trip(self, breaker):
        """Test that non-expected exceptions propagate without counting."""
        async def fail_func():
            raise ValueError("Programming error")

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        # Circuit should not trip on programming errors
        assert breaker.is_closed
        assert breaker.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_stats_returns_snapshot(self, breaker):
        """Test that stats returns an immutable snapshot."""
        s1 = breaker.stats
        s1.failure_count = 99  # Mutate the copy
        # Internal state should be unaffected
        assert breaker.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_reset(self, breaker):
        """Test that reset() clears state."""
        async def fail_func():
            raise ConnectionError("fail")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(fail_func)

        assert breaker.is_open

        await breaker.reset()
        assert breaker.is_closed
        assert breaker.stats.failure_count == 0

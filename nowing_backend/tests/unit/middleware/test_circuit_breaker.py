import time
from unittest.mock import AsyncMock, patch, ANY
import pytest
from app.agents.new_chat.middleware.circuit_breaker import (
    RedisCircuitBreaker,
    FAILURE_THRESHOLD,
    OPEN_COOLDOWN_SECONDS,
    PROBE_ALLOWED_TTL_SECONDS,
    STATE_KEY_TTL_SECONDS,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.incr.return_value = 1
    return redis


@pytest.mark.asyncio
async def test_cb_closed_initially(mock_redis):
    """Circuit breaker is CLOSED (is_open=False) when no failures are recorded."""
    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        assert await cb.is_open("test_source") is False
        mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_cb_records_failures_and_opens(mock_redis):
    """Circuit breaker opens after threshold is reached."""
    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()

        mock_redis.incr.return_value = FAILURE_THRESHOLD
        mock_redis.get.return_value = b"closed"

        await cb.record_failure("test_source")

        mock_redis.set.assert_any_call(
            "cb:open_until:test_source", ANY, ex=OPEN_COOLDOWN_SECONDS
        )
        mock_redis.set.assert_any_call(
            "cb:state:test_source", "open", ex=STATE_KEY_TTL_SECONDS
        )


@pytest.mark.asyncio
async def test_cb_is_open_when_key_exists(mock_redis):
    """is_open returns True if the open_until key is in the future."""
    future_time = time.time() + 10
    mock_redis.get.side_effect = [b"open", str(future_time).encode()]

    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        assert await cb.is_open("test_source") is True


@pytest.mark.asyncio
async def test_cb_resets_on_success(mock_redis):
    """record_success deletes the failure, open, state, and probe keys."""
    mock_redis.get.return_value = b"half_open"

    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        await cb.record_success("test_source")
        mock_redis.delete.assert_called_once_with(
            "cb:fail_count:test_source",
            "cb:open_until:test_source",
            "cb:state:test_source",
            "cb:probe_allowed:test_source",
        )


@pytest.mark.asyncio
async def test_cb_half_open_after_timeout(mock_redis):
    """After cooldown, is_open transitions to half_open and allows exactly one probe."""
    past_time = time.time() - 10
    # is_open() reads:
    #   1. state -> "open"
    #   2. open_until -> past_time (expired)
    # Then it issues SET NX on probe_allowed (returns True for the first caller),
    # transitions state to half_open, and DECRs probe_allowed (returns 0 -> allowed).
    mock_redis.get.side_effect = [b"open", str(past_time).encode()]
    mock_redis.set.return_value = True  # SET NX succeeded -> first probe slot created
    mock_redis.decr.return_value = 0  # First DECR -> probe allowed

    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        assert await cb.is_open("test_source") is False

        mock_redis.set.assert_any_call(
            "cb:probe_allowed:test_source",
            "1",
            nx=True,
            ex=PROBE_ALLOWED_TTL_SECONDS,
        )
        mock_redis.decr.assert_called_once_with("cb:probe_allowed:test_source")

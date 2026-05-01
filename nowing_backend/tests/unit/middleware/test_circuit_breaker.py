import time
from unittest.mock import AsyncMock, patch
import pytest
from app.agents.new_chat.middleware.circuit_breaker import RedisCircuitBreaker, FAILURE_THRESHOLD, OPEN_COOLDOWN_SECONDS

pytestmark = pytest.mark.unit

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    # Default behavior: keys don't exist
    redis.get.return_value = None
    redis.incr.return_value = 1
    return redis

@pytest.mark.asyncio
async def test_cb_closed_initially(mock_redis):
    """Circuit breaker is CLOSED (is_open=False) when no failures are recorded."""
    with patch("app.agents.new_chat.middleware.circuit_breaker.get_redis_client", return_value=mock_redis):
        cb = RedisCircuitBreaker()
        assert await cb.is_open("test_source") is False
        mock_redis.get.assert_called_once()

@pytest.mark.asyncio
async def test_cb_records_failures_and_opens(mock_redis):
    """Circuit breaker opens after threshold is reached."""
    with patch("app.agents.new_chat.middleware.circuit_breaker.get_redis_client", return_value=mock_redis):
        cb = RedisCircuitBreaker()
        
        # Simulate incrementing failure count to threshold
        mock_redis.incr.return_value = FAILURE_THRESHOLD
        
        await cb.record_failure("test_source")
        
        # Should call set with an expiration for the "open_until" key
        mock_redis.set.assert_called_once()
        args, kwargs = mock_redis.set.call_args
        assert args[0] == "cb:open_until:test_source"
        assert kwargs["ex"] == OPEN_COOLDOWN_SECONDS

@pytest.mark.asyncio
async def test_cb_is_open_when_key_exists(mock_redis):
    """is_open returns True if the open_until key is in the future."""
    future_time = time.time() + 10
    mock_redis.get.return_value = str(future_time).encode()
    
    with patch("app.agents.new_chat.middleware.circuit_breaker.get_redis_client", return_value=mock_redis):
        cb = RedisCircuitBreaker()
        assert await cb.is_open("test_source") is True

@pytest.mark.asyncio
async def test_cb_resets_on_success(mock_redis):
    """record_success deletes the failure and open keys."""
    with patch("app.agents.new_chat.middleware.circuit_breaker.get_redis_client", return_value=mock_redis):
        cb = RedisCircuitBreaker()
        await cb.record_success("test_source")
        mock_redis.delete.assert_called_once_with("cb:fail_count:test_source", "cb:open_until:test_source")

@pytest.mark.asyncio
async def test_cb_half_open_after_timeout(mock_redis):
    """is_open returns False (half-open/probing) if the timeout has passed."""
    past_time = time.time() - 10
    mock_redis.get.return_value = str(past_time).encode()
    
    with patch("app.agents.new_chat.middleware.circuit_breaker.get_redis_client", return_value=mock_redis):
        cb = RedisCircuitBreaker()
        assert await cb.is_open("test_source") is False

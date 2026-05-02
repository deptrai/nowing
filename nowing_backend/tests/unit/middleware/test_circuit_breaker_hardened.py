import time
import json
from unittest.mock import AsyncMock, patch, MagicMock, ANY
import pytest
from app.agents.new_chat.middleware.circuit_breaker import RedisCircuitBreaker, FAILURE_THRESHOLD, OPEN_COOLDOWN_SECONDS

pytestmark = pytest.mark.unit

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get.return_value = None
    redis.incr.return_value = 1
    redis.set.return_value = True
    redis.setnx.return_value = True
    redis.decr.return_value = 0
    return redis

@pytest.mark.asyncio
async def test_half_open_allows_only_one_probe(mock_redis):
    """AC1: Khi OPEN expired, request đầu tiên trả về False (HALF_OPEN probe), các request sau trả về True (block)."""
    with patch("app.agents.new_chat.middleware.circuit_breaker.get_redis_client", return_value=mock_redis):
        cb = RedisCircuitBreaker()
        source = "test_source"
        
        # Giả lập trạng thái OPEN đã expired trong Redis (open_until < current_time)
        past_time = time.time() - 10
        
        # Lần gọi 1: 
        # - get("cb:state:...") -> "open"
        # - get("cb:open_until:...") -> past_time
        # - decr("cb:probe_allowed:...") -> 0 (allow)
        mock_redis.get.side_effect = [b"open", str(past_time).encode()]
        mock_redis.decr.return_value = 0 
        assert await cb.is_open(source) is False
        
        # Lần gọi 2:
        # - get("cb:state:...") -> "half_open" (đã update từ lần 1)
        # - decr("cb:probe_allowed:...") -> -1 (block)
        mock_redis.get.side_effect = [b"half_open"]
        mock_redis.decr.return_value = -1
        assert await cb.is_open(source) is True

@pytest.mark.asyncio
async def test_half_open_success_closes_circuit(mock_redis):
    """AC2: Probe thành công -> CLOSE circuit."""
    with patch("app.agents.new_chat.middleware.circuit_breaker.get_redis_client", return_value=mock_redis):
        cb = RedisCircuitBreaker()
        source = "test_source"
        
        # Mock state ban đầu là half_open
        mock_redis.get.return_value = b"half_open"
        
        await cb.record_success(source)
        
        # Verify state updated to closed
        mock_redis.set.assert_any_call(f"cb:state:{source}", "closed")
        # Verify keys deleted
        mock_redis.delete.assert_called_with("cb:fail_count:test_source", "cb:open_until:test_source", "cb:state:test_source", "cb:probe_allowed:test_source")

@pytest.mark.asyncio
async def test_half_open_failure_reopens_circuit(mock_redis):
    """AC3: Probe thất bại -> OPEN circuit lại."""
    with patch("app.agents.new_chat.middleware.circuit_breaker.get_redis_client", return_value=mock_redis):
        cb = RedisCircuitBreaker()
        source = "test_source"
        
        # Giả lập đang ở state half_open
        mock_redis.get.return_value = b"half_open"
        
        # Mock logic record_failure
        await cb.record_failure(source)
        
        # Verify open_until set again
        mock_redis.set.assert_any_call(f"cb:open_until:{source}", ANY, ex=OPEN_COOLDOWN_SECONDS)
        # Verify state updated to open
        mock_redis.set.assert_any_call(f"cb:state:{source}", "open")

@pytest.mark.asyncio
async def test_redis_down_returns_last_known_state(mock_redis):
    """AC4: Redis down -> Trả về last-known state từ in-memory cache."""
    with patch("app.agents.new_chat.middleware.circuit_breaker.get_redis_client", return_value=mock_redis):
        cb = RedisCircuitBreaker()
        source = "test_source"
        
        # 1. Update cache thành công: CLOSED
        mock_redis.get.return_value = None 
        assert await cb.is_open(source) is False
        
        # 2. Redis down -> Trả về False
        mock_redis.get.side_effect = Exception("Redis connection lost")
        assert await cb.is_open(source) is False 
            
        # 3. Giả lập circuit OPEN thành công
        future_time = time.time() + 10
        mock_redis.get.side_effect = None
        mock_redis.get.side_effect = [b"open", str(future_time).encode()]
        assert await cb.is_open(source) is True # Update cache to True
        
        # 4. Redis down lần nữa -> Trả về True
        mock_redis.get.side_effect = Exception("Redis connection lost")
        assert await cb.is_open(source) is True

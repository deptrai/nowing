"""Unit tests for RedisRunEventBus (td-2: Redis event bus subscribe failure state leak)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.capabilities.core.events_redis import (
    RedisRunEventBus,
    _channel,
    _run_id_from_channel,
)


@pytest.mark.asyncio
async def test_run_id_and_channel_helpers():
    assert _channel("123") == "nowing:run:123"
    assert _run_id_from_channel("nowing:run:123") == "123"
    assert _run_id_from_channel("invalid:channel") == ""


@pytest.mark.asyncio
async def test_subscribe_creates_queue_and_registers_subscriber():
    bus = RedisRunEventBus(buffer_size=10, subscriber_queue_size=10)
    mock_redis = MagicMock()
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_redis.pubsub.return_value = mock_pubsub
    bus._redis = mock_redis

    queue = bus.subscribe("run-1")
    assert isinstance(queue, asyncio.Queue)
    assert queue in bus._subscribers["run-1"]

    # Allow fire-and-forget tasks to execute
    await asyncio.sleep(0.05)

    bus.unsubscribe("run-1", queue)
    assert "run-1" not in bus._subscribers


@pytest.mark.asyncio
async def test_subscribe_failure_triggers_recovery():
    """td-2: On subscribe timeout or error, bus triggers handle_listener_error to recover."""
    bus = RedisRunEventBus(buffer_size=10, subscriber_queue_size=10)
    mock_redis = MagicMock()
    mock_pubsub = MagicMock()
    # Simulate timeout on subscribe
    mock_pubsub.subscribe = AsyncMock(side_effect=TimeoutError("subscribe timed out"))
    mock_pubsub.close = AsyncMock()
    mock_redis.pubsub.return_value = mock_pubsub
    bus._redis = mock_redis

    with patch.object(
        bus, "_handle_listener_error", new_callable=AsyncMock
    ) as mock_handle_error:
        queue = bus.subscribe("run-timeout")
        assert queue in bus._subscribers["run-timeout"]

        # Wait for fire-and-forget _sub task
        await asyncio.sleep(0.05)

        assert mock_handle_error.call_count >= 1

    bus.unsubscribe("run-timeout", queue)


@pytest.mark.asyncio
async def test_publish_fans_out_to_local_queue_and_buffer():
    bus = RedisRunEventBus(buffer_size=10, subscriber_queue_size=10)
    mock_redis = MagicMock()
    mock_redis.publish = AsyncMock()
    bus._redis = mock_redis

    queue = bus.subscribe("run-2")
    event = {"type": "progress", "percent": 50}

    bus.publish("run-2", event)

    received = queue.get_nowait()
    assert received == event
    assert bus.replay("run-2") == [event]

    bus.close("run-2")
    assert "run-2" not in bus._subscribers
    assert "run-2" not in bus._buffers

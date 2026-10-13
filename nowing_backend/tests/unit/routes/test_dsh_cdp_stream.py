"""Unit tests for CDP stream SSE heartbeat and cleanup (Story 35.3 / Retro Action Item 2)."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from app.auth.context import AuthContext
from app.db import User
from app.routes.dsh_routes import cdp_stream

pytestmark = [pytest.mark.unit]


def _make_mock_auth() -> AuthContext:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    auth = MagicMock(spec=AuthContext)
    auth.user = user
    return auth


@pytest.mark.asyncio
async def test_cdp_stream_heartbeat_idle_30s():
    """Verify that an idle stream over 30s receives at least 2 keep-alive ping comments."""
    auth = _make_mock_auth()

    # Time generator simulating:
    # 0s: initial start
    # 1s: loop iteration 1
    # 16s: loop iteration 2 (elapsed 16s >= 15s -> yields ping 1, updates last_heartbeat to 16)
    # 32s: loop iteration 3 (elapsed 16s >= 15s -> yields ping 2, updates last_heartbeat to 32)
    # 33s: disconnect
    timestamps = [0.0, 1.0, 16.0, 32.0, 33.0, 34.0, 35.0]
    ts_idx = 0

    def mock_time():
        nonlocal ts_idx
        val = timestamps[min(ts_idx, len(timestamps) - 1)]
        ts_idx += 1
        return val

    # Disconnect after emitting 2 pings (at loop iteration 4)
    disconnected_calls = [False, False, False, False, True]
    disc_idx = 0

    async def mock_is_disconnected():
        nonlocal disc_idx
        val = disconnected_calls[min(disc_idx, len(disconnected_calls) - 1)]
        disc_idx += 1
        return val

    mock_request = MagicMock(spec=Request)
    mock_request.is_disconnected = mock_is_disconnected

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = AsyncMock(return_value=None)
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)

    with (
        patch(
            "app.routes.dsh_routes.get_redis_client", AsyncMock(return_value=mock_redis)
        ),
        patch("app.routes.dsh_routes.time.monotonic", side_effect=mock_time),
    ):
        response = await cdp_stream(mock_request, auth=auth)

        yielded_items = []
        async for item in response.body_iterator:
            yielded_items.append(item)

        # Confirm at least 2 ping comments received
        ping_comments = [
            item
            for item in yielded_items
            if item == "comment: ping\r\n\r\n" or "ping" in str(item)
        ]
        assert len(ping_comments) >= 2

        # Verify Redis and pubsub cleanup
        channel = f"cdp_stream:{auth.user.id}"
        stream_lock_key = f"cdp:stream:lock:{auth.user.id}"
        mock_pubsub.unsubscribe.assert_awaited_once_with(channel)
        mock_pubsub.close.assert_awaited_once()
        mock_redis.delete.assert_awaited_once_with(stream_lock_key)


@pytest.mark.asyncio
async def test_cdp_stream_disconnect_cleans_up_pubsub_and_lock():
    """Verify that midway disconnect properly executes finally block cleanup."""
    auth = _make_mock_auth()

    # Disconnected immediately on second check
    call_count = 0

    async def mock_is_disconnected():
        nonlocal call_count
        call_count += 1
        return call_count > 1

    mock_request = MagicMock(spec=Request)
    mock_request.is_disconnected = mock_is_disconnected

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = AsyncMock(return_value=None)
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)

    with patch(
        "app.routes.dsh_routes.get_redis_client", AsyncMock(return_value=mock_redis)
    ):
        response = await cdp_stream(mock_request, auth=auth)

        async for _ in response.body_iterator:
            pass

        channel = f"cdp_stream:{auth.user.id}"
        stream_lock_key = f"cdp:stream:lock:{auth.user.id}"
        mock_pubsub.unsubscribe.assert_awaited_once_with(channel)
        mock_pubsub.close.assert_awaited_once()
        mock_redis.delete.assert_awaited_once_with(stream_lock_key)


@pytest.mark.asyncio
async def test_cdp_stream_cancellation_cleans_up():
    """Verify that asyncio.CancelledError during stream cleanup still releases resources."""
    auth = _make_mock_auth()

    async def mock_get_message(*args, **kwargs):
        raise asyncio.CancelledError()

    mock_request = MagicMock(spec=Request)
    mock_request.is_disconnected = AsyncMock(return_value=False)

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = mock_get_message
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)

    with patch(
        "app.routes.dsh_routes.get_redis_client", AsyncMock(return_value=mock_redis)
    ):
        response = await cdp_stream(mock_request, auth=auth)

        with pytest.raises(asyncio.CancelledError):
            async for _ in response.body_iterator:
                pass

        channel = f"cdp_stream:{auth.user.id}"
        stream_lock_key = f"cdp:stream:lock:{auth.user.id}"
        mock_pubsub.unsubscribe.assert_awaited_once_with(channel)
        mock_pubsub.close.assert_awaited_once()
        mock_redis.delete.assert_awaited_once_with(stream_lock_key)


@pytest.mark.asyncio
async def test_cdp_stream_cleanup_deletes_lock_when_unsubscribe_raises():
    """Verify that stream_lock is deleted even if pubsub.unsubscribe raises an error."""
    auth = _make_mock_auth()

    mock_request = MagicMock(spec=Request)
    mock_request.is_disconnected = AsyncMock(return_value=True)

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = AsyncMock(return_value=None)
    mock_pubsub.unsubscribe = AsyncMock(
        side_effect=RuntimeError("PubSub connection broken")
    )
    mock_pubsub.close = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)

    with patch(
        "app.routes.dsh_routes.get_redis_client", AsyncMock(return_value=mock_redis)
    ):
        response = await cdp_stream(mock_request, auth=auth)

        async for _ in response.body_iterator:
            pass

        channel = f"cdp_stream:{auth.user.id}"
        stream_lock_key = f"cdp:stream:lock:{auth.user.id}"
        mock_pubsub.unsubscribe.assert_awaited_once_with(channel)
        mock_pubsub.close.assert_awaited_once()
        mock_redis.delete.assert_awaited_once_with(stream_lock_key)

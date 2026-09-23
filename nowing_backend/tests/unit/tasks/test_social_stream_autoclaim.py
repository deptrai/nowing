"""Unit tests for XAUTOCLAIM in social_stream_worker (Story 35.1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.social_stream_worker import (
    AUTOCLAIM_MIN_IDLE_TIME_MS,
    run_social_stream_consumer,
)

pytestmark = [pytest.mark.unit]


@pytest.mark.asyncio
async def test_consume_social_stream_calls_xautoclaim():
    """consume_social_stream should call xautoclaim to recover pending PEL messages."""
    redis_mock = AsyncMock()

    # Mock xgroup_create failure (already exists)
    from redis.exceptions import ResponseError
    redis_mock.xgroup_create.side_effect = ResponseError("BUSYGROUP Consumer Group name already exists")

    # Mock xautoclaim returning a claimed message
    msg_payload = {
        "event_id": "evt-1",
        "post_id": "post-1",
        "platform": "facebook",
        "author_name": "Test Author",
        "text": "Looking for real estate in District 1",
        "created_at": "2026-09-17T00:00:00Z",
    }
    redis_mock.xautoclaim.return_value = ("0-0", [("1600000000000-0", msg_payload)], [])

    with patch("app.tasks.social_stream_worker.async_session_maker") as mock_session_maker:
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        # Pass mock redis_client directly
        await run_social_stream_consumer(redis_client=redis_mock, batch_size=1, max_loops=1)

    redis_mock.xautoclaim.assert_awaited_once()
    call_kwargs = redis_mock.xautoclaim.call_args.kwargs
    assert call_kwargs["min_idle_time"] == AUTOCLAIM_MIN_IDLE_TIME_MS

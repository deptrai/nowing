"""Unit tests for XAUTOCLAIM in social_stream_worker (Story 35.1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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

    redis_mock.xgroup_create.side_effect = ResponseError(
        "BUSYGROUP Consumer Group name already exists"
    )

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

    with patch(
        "app.tasks.social_stream_worker.async_session_maker"
    ) as mock_session_maker:
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        # Pass mock redis_client directly
        await run_social_stream_consumer(
            redis_client=redis_mock, batch_size=1, max_loops=1
        )

    redis_mock.xautoclaim.assert_awaited_once()
    call_kwargs = redis_mock.xautoclaim.call_args.kwargs
    assert call_kwargs["min_idle_time"] == AUTOCLAIM_MIN_IDLE_TIME_MS


@pytest.mark.asyncio
async def test_xautoclaim_cursor_rescan_tracks_and_resets_cursor():
    """XAUTOCLAIM should advance cursor on subsequent iterations and reset to 0-0 when completed or on error."""
    from redis.exceptions import ResponseError

    redis_mock = AsyncMock()
    redis_mock.xgroup_create.side_effect = ResponseError("BUSYGROUP")
    redis_mock.xpending_range.return_value = []
    redis_mock.xreadgroup.return_value = []

    msg_payload = {
        "event_id": "evt-1",
        "post_id": "post-1",
        "platform": "facebook",
        "author_name": "Test Author",
        "text": "Property query",
        "created_at": "2026-09-17T00:00:00Z",
        "workspace_id": 1,
    }

    # Loop 1: returns cursor "1600000001000-0"
    # Loop 2: completes scan, returns cursor "0-0"
    # Loop 3: starts at "0-0" again
    redis_mock.xautoclaim.side_effect = [
        ("1600000001000-0", [("1600000000000-0", msg_payload)]),
        ("0-0", [("1600000001000-0", msg_payload)]),
        ("1600000002000-0", [("1600000002000-0", msg_payload)]),
    ]

    with (
        patch(
            "app.tasks.social_stream_worker.async_session_maker"
        ) as mock_session_maker,
        patch(
            "app.tasks.social_stream_worker.process_social_post_event", return_value=1
        ),
        patch("app.tasks.social_stream_worker.BATCH_SLEEP_SECONDS", 0),
    ):
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        await run_social_stream_consumer(
            redis_client=redis_mock, batch_size=1, max_loops=3
        )

    assert redis_mock.xautoclaim.await_count == 3
    calls = redis_mock.xautoclaim.await_args_list
    assert calls[0].kwargs["start_id"] == "0-0"
    assert calls[1].kwargs["start_id"] == "1600000001000-0"
    assert calls[2].kwargs["start_id"] == "0-0"


@pytest.mark.asyncio
async def test_xautoclaim_cursor_resets_on_exception():
    """XAUTOCLAIM cursor should reset to 0-0 on exception."""
    from redis.exceptions import ResponseError

    redis_mock = AsyncMock()
    redis_mock.xgroup_create.side_effect = ResponseError("BUSYGROUP")
    redis_mock.xpending_range.return_value = []

    msg_payload = {
        "event_id": "evt-1",
        "post_id": "post-1",
        "platform": "facebook",
        "author_name": "Test Author",
        "text": "Property query",
        "content": "Property query",
        "content_snippet": "Property query",
        "created_at": "2026-09-17T00:00:00Z",
        "workspace_id": 1,
        "target_id": 1,
    }

    # In loop 2, xautoclaim raises an exception. xreadgroup provides an entry so loop continues to loop 3.
    redis_mock.xreadgroup.return_value = [
        ("stream:social:raw_posts", [("1600000001500-0", msg_payload)])
    ]

    # Loop 1: returns cursor "1600000001000-0"
    # Loop 2: raises an exception during xautoclaim
    # Loop 3: should reset and pass "0-0"
    redis_mock.xautoclaim.side_effect = [
        ("1600000001000-0", [("1600000000000-0", msg_payload)]),
        RuntimeError("Redis connection flicker"),
        ("0-0", [("1600000002000-0", msg_payload)]),
    ]

    with (
        patch(
            "app.tasks.social_stream_worker.async_session_maker"
        ) as mock_session_maker,
        patch(
            "app.tasks.social_stream_worker.process_social_post_event", return_value=1
        ),
        patch("app.tasks.social_stream_worker.BATCH_SLEEP_SECONDS", 0),
    ):
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        await run_social_stream_consumer(
            redis_client=redis_mock, batch_size=1, max_loops=3
        )

    assert redis_mock.xautoclaim.await_count == 3
    calls = redis_mock.xautoclaim.await_args_list
    assert calls[0].kwargs["start_id"] == "0-0"
    assert calls[1].kwargs["start_id"] == "1600000001000-0"
    assert calls[2].kwargs["start_id"] == "0-0"

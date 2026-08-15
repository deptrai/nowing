"""Integration tests for Redis Stream social posts buffer & processor (Story 21.8 / Task 6.3)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.tasks.social_stream_worker import process_social_post_event


@pytest.mark.asyncio
async def test_social_redis_stream_event_processing():
    """Verify event payload from Redis stream is parsed, entities extracted, and saved."""
    raw_event_payload = {
        "platform": "facebook",
        "external_post_id": "fb_stream_001",
        "author_id": "usr_999",
        "author_name": "Trần Thị B",
        "content": "Bán gấp nhà mặt tiền Quận 1 giá 25 tỷ, liên hệ o909123456 chính chủ.",
        "post_url": "https://facebook.com/groups/bds/posts/001",
        "reactions_count": "50",
        "comments_count": "12",
        "shares_count": "3",
        "published_at": "2026-08-15T09:30:00Z",
    }

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.tasks.social_stream_worker.get_async_session", return_value=mock_db):
        processed = await process_social_post_event(raw_event_payload, session=mock_db)
        assert processed["platform"] == "facebook"
        assert processed["external_post_id"] == "fb_stream_001"
        assert "0909123456" in processed["raw_entities"]["phones"]
        assert processed["intent_tag"] == "sell"
        assert processed["fit_score"] > 0

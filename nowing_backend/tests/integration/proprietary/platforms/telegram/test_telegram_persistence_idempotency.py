"""Integration test for Telegram message idempotent upsert (Story 22.1 / AC-4 / AD-5).

Verifies that re-scraping the same (channel_id, message_id) updates the existing
row instead of creating a duplicate.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.mark.skip(reason="RED PHASE: TelegramMessage.upsert() not yet implemented")
async def test_telegram_message_upsert_is_idempotent(db_session: AsyncSession) -> None:
    """AC-4: ON CONFLICT (channel_id, message_id) DO UPDATE without duplicates."""
    from app.proprietary.platforms.telegram.models import (
        TelegramChannel,
        TelegramMessage,
    )

    channel = TelegramChannel(
        username="bds_hanoi",
        title="BĐS Hà Nội",
        about="Chính chủ",
    )
    db_session.add(channel)
    await db_session.flush()

    # First scrape: insert the message
    msg1 = await TelegramMessage.upsert(
        db_session,
        channel_id=channel.id,
        message_id=1001,
        date=datetime(2026, 8, 15, 8, 30, 0, tzinfo=UTC),
        text="Bán nhà Cầu Giấy 12.5 tỷ",
        views=100,
        forwards=0,
        replies_count=0,
        raw_entities=[{"type": "phone", "value": "0912345678"}],
        intent_tag="sell",
        has_media=False,
    )

    # Second scrape: same (channel_id, message_id) with updated fields
    msg2 = await TelegramMessage.upsert(
        db_session,
        channel_id=channel.id,
        message_id=1001,
        date=datetime(2026, 8, 15, 8, 30, 0, tzinfo=UTC),
        text="Bán nhà Cầu Giấy 12.5 tỷ (cập nhật)",
        views=250,
        forwards=5,
        replies_count=2,
        raw_entities=[
            {"type": "phone", "value": "0912345678"},
            {"type": "price", "value": "12.5 tỷ"},
        ],
        intent_tag="sell",
        has_media=True,
    )

    # The same row should be reused
    assert msg1.id == msg2.id

    rows = (
        await db_session.execute(
            select(TelegramMessage).where(
                TelegramMessage.channel_id == channel.id,
                TelegramMessage.message_id == 1001,
            )
        )
    ).scalars().all()
    assert len(rows) == 1

    stored = rows[0]
    assert stored.text == "Bán nhà Cầu Giấy 12.5 tỷ (cập nhật)"
    assert stored.views == 250
    assert stored.forwards == 5
    assert stored.replies_count == 2
    assert stored.has_media is True
    assert stored.intent_tag == "sell"
    assert len(stored.raw_entities) == 2

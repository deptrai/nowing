"""Unit tests for Telegram Capability & MCP Tool Registration (Story 22.1 / AD-1, AD-6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.capabilities.telegram.search.definition import TELEGRAM_SEARCH
from app.capabilities.telegram.search.schemas import (
    TelegramSearchInput,
    TelegramSearchOutput,
)
from app.mcp_tools import MCP_TOOL_CATALOG, McpToolGroup
from app.proprietary.platforms.telegram.schemas import (
    ExtractedEntities,
    TelegramChannelInfo,
    TelegramMessageParsed,
    TelegramScrapeResult,
)


def test_mcp_tool_catalog_contains_telegram_search() -> None:
    """Check that nowing_telegram_search_messages is registered in MCP tool catalog."""
    matching_tools = [
        t for t in MCP_TOOL_CATALOG if t["name"] == "nowing_telegram_search_messages"
    ]
    assert len(matching_tools) == 1
    assert matching_tools[0]["group"] == McpToolGroup.SCRAPER


@pytest.mark.asyncio
async def test_telegram_search_capability_executor() -> None:
    """Capability executor fetches channel messages and filters by keyword/intent."""
    mock_messages = [
        TelegramMessageParsed(
            message_id=1001,
            channel_username="batdongsanhanoi",
            text="Bán nhà mặt phố Cầu Giấy 12.5 tỷ. LH: 0912345678",
            published_at="2026-08-15T08:30:00Z",
            views=1500,
            has_media=True,
            author_name="Admin BĐS",
            intent_tag="sell",
            entities=ExtractedEntities(
                phone_numbers=["0912345678"],
                emails=[],
                prices=["12.5 tỷ"],
                hashtags=["#bds"],
                intent_tag="sell",
                raw_entities=[{"type": "phone", "value": "0912345678"}],
            ),
        ),
        TelegramMessageParsed(
            message_id=1002,
            channel_username="batdongsanhanoi",
            text="Cần mua đất Đông Anh tài chính 3 tỷ",
            published_at="2026-08-15T09:00:00Z",
            views=600,
            has_media=False,
            author_name="Member",
            intent_tag="buy",
            entities=ExtractedEntities(
                phone_numbers=[],
                emails=[],
                prices=["3 tỷ"],
                hashtags=[],
                intent_tag="buy",
                raw_entities=[],
            ),
        ),
    ]

    mock_result = TelegramScrapeResult(
        channel_info=TelegramChannelInfo(
            username="batdongsanhanoi",
            title="Bất Động Sản Hà Nội 2026",
            description="Kênh BĐS chính chủ",
            subscribers_count=25000,
        ),
        messages=mock_messages,
    )

    with patch(
        "app.capabilities.telegram.search.executor.scrape_telegram_channel",
        new=AsyncMock(return_value=mock_result),
    ):
        # 1. Search without filters
        payload = TelegramSearchInput(
            channel_username="batdongsanhanoi",
            limit=10,
        )
        output: TelegramSearchOutput = await TELEGRAM_SEARCH.executor(payload)

        assert output.total_found == 2
        assert len(output.messages) == 2
        assert output.channel_info.username == "batdongsanhanoi"
        assert output.messages[0].intent_tag == "sell"
        assert "0912345678" in output.messages[0].entities.phone_numbers

        # 2. Filter by intent "sell"
        payload_sell = TelegramSearchInput(
            channel_username="batdongsanhanoi",
            intent="sell",
            limit=10,
        )
        output_sell: TelegramSearchOutput = await TELEGRAM_SEARCH.executor(payload_sell)
        assert output_sell.total_found == 1
        assert output_sell.messages[0].message_id == 1001

        # 3. Filter by keyword "Đông Anh"
        payload_kw = TelegramSearchInput(
            channel_username="batdongsanhanoi",
            keyword="Đông Anh",
            limit=10,
        )
        output_kw: TelegramSearchOutput = await TELEGRAM_SEARCH.executor(payload_kw)
        assert output_kw.total_found == 1
        assert output_kw.messages[0].message_id == 1002


def test_telegram_search_billable_units_and_validation() -> None:
    """Test billable_units is 0 when empty and validation rejects bad username."""
    empty_output = TelegramSearchOutput(messages=[], total_found=0)
    assert empty_output.billable_units == 0

    valid_input = TelegramSearchInput(channel_username="https://t.me/s/batdongsanhanoi")
    assert valid_input.channel_username == "batdongsanhanoi"

    with pytest.raises(ValueError, match="Invalid Telegram channel username"):
        TelegramSearchInput(channel_username="inv!@#name")


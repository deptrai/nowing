"""Unit tests for Telegram AI Agent Tools (Story 22.3 / AC-4).

Validates agent tools: `telegram_search_channel` and `telegram_fetch_recent_posts`,
ensuring query filtering, entity formatting, and schema compatibility with Nowing AI Assistant.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# AC-4: Telegram AI Agent Chat Tools
# ---------------------------------------------------------------------------


class TestTelegramAgentTools:
    """Validate AI Agent tools for searching and reading Telegram channels."""

    @pytest.mark.asyncio
    async def test_telegram_search_channel_tool(self) -> None:
        """telegram_search_channel tool must return formatted post summaries with extracted entities."""
        from app.capabilities.telegram.tools import telegram_search_channel

        mock_results = [
            {
                "channel_username": "bds_hanoi_chinhchu",
                "message_id": 4567,
                "message_text": "Bán gấp nhà phố Trung Kính, Cầu Giấy 55m2 x 5 tầng, 12.5 tỷ. LH: 0912.345.678",
                "posted_at": "2026-08-15T14:30:00Z",
                "views_count": 1240,
                "raw_entities": {
                    "phones": ["0912345678"],
                    "prices": [{"raw_text": "12.5 tỷ", "amount_vnd": 12_500_000_000}],
                    "locations": ["Cầu Giấy, Hà Nội"],
                },
            }
        ]

        with patch("app.capabilities.telegram.tools.query_telegram_messages", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = mock_results

            result = await telegram_search_channel(
                channel="bds_hanoi_chinhchu",
                query="Trung Kính",
                limit=5,
            )

            assert "0912345678" in result or "0912.345.678" in result
            assert "12.5 tỷ" in result or "12.5 Tỷ" in result
            assert "1240" in result
            mock_db.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_telegram_fetch_recent_posts_tool(self) -> None:
        """telegram_fetch_recent_posts tool must return chronological list of recent posts."""
        from app.capabilities.telegram.tools import telegram_fetch_recent_posts

        mock_results = [
            {
                "channel_username": "nhadat_saigon",
                "message_id": 1001,
                "message_text": "Cho thuê mặt bằng Quận 1 35 triệu/tháng",
                "posted_at": "2026-08-15T16:00:00Z",
                "views_count": 500,
                "raw_entities": {"phones": [], "prices": [{"raw_text": "35 triệu/tháng"}]},
            }
        ]

        with patch("app.capabilities.telegram.tools.query_telegram_messages", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = mock_results

            result = await telegram_fetch_recent_posts(
                channel="nhadat_saigon",
                limit=10,
            )

            assert "35 triệu/tháng" in result
            assert "nhadat_saigon" in result
            mock_db.assert_awaited_once()

    def test_tools_registered_in_agent_tool_registry(self) -> None:
        """Telegram tools must be registered in the core agent tool definition catalog."""
        from app.capabilities.core.access.agent import ALL_AVAILABLE_TOOLS

        tool_names = [tool.name for tool in ALL_AVAILABLE_TOOLS]
        assert "telegram_search_channel" in tool_names
        assert "telegram_fetch_recent_posts" in tool_names

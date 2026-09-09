"""Unit tests for XActionsSocialAdapterV2."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.proprietary.platforms.xactions.adapter_v2 import (
    UniversalScrapeTargetMapper,
    XActionsSocialAdapterV2,
)


class FakeTarget:
    def __init__(self, platform, target_id, account_id=None, proxy_url=None):
        self.platform = platform
        self.target_id = target_id
        self.account_id = account_id
        self.proxy_url = proxy_url


class TestUniversalScrapeTargetMapper:
    def test_map_facebook_group(self):
        target = FakeTarget("facebook_group", "honda_scoopy")
        tool, args = UniversalScrapeTargetMapper.map(target)
        assert tool == "x_facebook_group_posts"
        assert args["url"].endswith("/groups/honda_scoopy")

    def test_map_tiktok_hashtag(self):
        target = FakeTarget("tiktok_hashtag", "bds")
        tool, args = UniversalScrapeTargetMapper.map(target)
        assert tool == "x_scrape"
        assert args["platform"] == "tiktok"

    def test_map_unsupported_raises(self):
        target = FakeTarget("unknown_platform", "x")
        with pytest.raises(ValueError):
            UniversalScrapeTargetMapper.map(target)

    def test_fallback_crawl_post_rejects_non_url(self):
        target = FakeTarget("facebook_page", "my_page")
        with pytest.raises(ValueError, match="valid HTTP"):
            UniversalScrapeTargetMapper.fallback_crawl_post(target)

    def test_fallback_crawl_post_accepts_url(self):
        target = FakeTarget("facebook_page", "https://facebook.com/my_page")
        tool, args = UniversalScrapeTargetMapper.fallback_crawl_post(target)
        assert tool == "x_crawl_post"
        assert args["url"].startswith("https://")


class TestXActionsSocialAdapterV2:
    @pytest.mark.asyncio
    async def test_fetch_posts_for_target_sets_dry_run_false(self):
        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        target = FakeTarget("shopee_keyword", "laptop")

        _ = await adapter.fetch_posts_for_target(target)

        call_args = client._session.call_tool.call_args
        assert call_args[0][0] == "x_scrape"
        assert call_args.kwargs["arguments"]["dryRun"] is False

    @pytest.mark.asyncio
    async def test_fetch_posts_for_target_includes_account_id(self):
        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        target = FakeTarget("facebook_group", "honda", account_id="fb_01")

        await adapter.fetch_posts_for_target(target)

        call_args = client._session.call_tool.call_args
        assert call_args.kwargs["arguments"]["accountId"] == "fb_01"

    @pytest.mark.asyncio
    async def test_fetch_posts_for_target_includes_proxy_url(self):
        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        target = FakeTarget("facebook_group", "honda", proxy_url="socks5://proxy:1080")

        await adapter.fetch_posts_for_target(target)

        call_args = client._session.call_tool.call_args
        assert call_args.kwargs["arguments"]["proxyUrl"] == "socks5://proxy:1080"


class XActionsMcpClientWithAdmin:
    """Fake client that passes call_tool through."""

    def __init__(self):
        self.admin_token = "admin"
        self._session = MagicMock()
        self._session.call_tool = AsyncMock(
            return_value=MagicMock(
                isError=False,
                content=[MagicMock(text='{"success": true, "data": []}')],
            )
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def call_tool(self, tool_name: str, arguments: dict):
        return await self._session.call_tool(tool_name, arguments=arguments)

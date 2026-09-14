"""Unit tests for XActionsSocialAdapterV2."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.proprietary.platforms.xactions.adapter_v2 import (
    TargetUnsupportedError,
    UniversalScrapeTargetMapper,
    XActionsSocialAdapterV2,
)
from app.proprietary.platforms.xactions.mcp_client import XActionsMcpError


class FakeTarget:
    def __init__(
        self,
        platform,
        target_id,
        account_id=None,
        proxy_url=None,
        id=1,
        target_url=None,
    ):
        self.id = id
        self.platform = platform
        self.target_id = target_id
        self.target_url = target_url
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
        with pytest.raises(TargetUnsupportedError, match="lacks valid HTTP"):
            UniversalScrapeTargetMapper.fallback_crawl_post(target)

    def test_fallback_crawl_post_accepts_url(self):
        target = FakeTarget("facebook_page", "https://facebook.com/my_page")
        tool, args = UniversalScrapeTargetMapper.fallback_crawl_post(target)
        assert tool == "x_crawl_post"
        assert args["url"].startswith("https://")
        assert args["platform"] == "facebook"

    def test_fallback_crawl_post_rejects_missing_platform(self):
        target = FakeTarget("", "https://facebook.com/my_page")
        with pytest.raises(TargetUnsupportedError, match="lacks valid platform"):
            UniversalScrapeTargetMapper.fallback_crawl_post(target)


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

    @pytest.mark.asyncio
    async def test_fetch_posts_for_target_fallback_on_xact_404_success(self):
        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        target = FakeTarget(
            platform="chotot_category",
            target_id="https://www.chotot.com/mua-ban-laptop",
            account_id="ct_01",
            proxy_url="http://proxy:8080",
        )

        async def _call_tool(tool_name, arguments):
            if tool_name == "x_scrape":
                raise XActionsMcpError(
                    message="Tool x_scrape not found",
                    code="XACT_404",
                )
            if tool_name == "x_crawl_post":
                return {
                    "success": True,
                    "data": [
                        {
                            "id": "post_123",
                            "content": "Laptop Dell XPS thanh ly",
                            "authorName": "Nguyen Van A",
                            "postUrl": "https://www.chotot.com/post_123",
                        }
                    ],
                }
            raise AssertionError(f"Unexpected tool call: {tool_name}")

        client.call_tool = AsyncMock(side_effect=_call_tool)

        posts = await adapter.fetch_posts_for_target(target)

        assert len(posts) == 1
        assert posts[0].external_post_id == "post_123"
        assert posts[0].platform == "chotot"
        assert posts[0].content == "Laptop Dell XPS thanh ly"
        assert posts[0].author_name == "Nguyen Van A"
        assert posts[0].post_url == "https://www.chotot.com/post_123"

        # Verify fallback arguments passed
        assert client.call_tool.call_count == 2
        fallback_call = client.call_tool.call_args_list[1]
        assert fallback_call[0][0] == "x_crawl_post"
        assert fallback_call[0][1] == {
            "platform": "chotot",
            "url": "https://www.chotot.com/mua-ban-laptop",
            "accountId": "ct_01",
            "proxyUrl": "http://proxy:8080",
            "dryRun": False,
        }

    @pytest.mark.asyncio
    async def test_fetch_posts_for_target_fallback_accepts_single_dict_data(self):
        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        target = FakeTarget(
            platform="chotot_category",
            target_id="https://www.chotot.com/mua-ban-laptop/123",
        )

        async def _call_tool(tool_name, arguments):
            if tool_name == "x_scrape":
                raise XActionsMcpError("Not found", code="XACT_404")
            assert tool_name == "x_crawl_post"
            return {
                "success": True,
                "data": {
                    "postId": "ct_single_post",
                    "text": "Single post content",
                    "url": "https://www.chotot.com/mua-ban-laptop/123",
                },
            }

        client.call_tool = AsyncMock(side_effect=_call_tool)

        posts = await adapter.fetch_posts_for_target(target)
        assert client.call_tool.call_count == 2
        assert len(posts) == 1
        assert posts[0].external_post_id == "ct_single_post"
        assert posts[0].content == "Single post content"
        assert posts[0].post_url == "https://www.chotot.com/mua-ban-laptop/123"

    @pytest.mark.asyncio
    async def test_fetch_posts_for_target_fallback_non_url_raises_target_unsupported(self):
        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        target = FakeTarget(
            platform="shopee_keyword",
            target_id="laptop",
        )

        client.call_tool = AsyncMock(
            side_effect=XActionsMcpError("Tool x_scrape not found", code="XACT_404")
        )

        with pytest.raises(TargetUnsupportedError, match="lacks valid HTTP"):
            await adapter.fetch_posts_for_target(target)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fallback_code", ["XACT_404", "XACT_4001", "tool_not_found"])
    async def test_fetch_posts_for_target_fallback_permanent_error_raises_target_unsupported(
        self, fallback_code
    ):
        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        target = FakeTarget(
            platform="chotot_category",
            target_id="https://www.chotot.com/mua-ban-laptop",
        )

        async def _call_tool(tool_name, arguments):
            if tool_name == "x_scrape":
                raise XActionsMcpError("Tool x_scrape not found", code="XACT_404")
            raise XActionsMcpError(f"Fallback failed: {fallback_code}", code=fallback_code)

        client.call_tool = AsyncMock(side_effect=_call_tool)

        with pytest.raises(TargetUnsupportedError, match=f"failed permanently with code {fallback_code}"):
            await adapter.fetch_posts_for_target(target)

    @pytest.mark.asyncio
    async def test_fetch_posts_for_target_fallback_transient_rate_limit_reraised(self):
        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        target = FakeTarget(
            platform="chotot_category",
            target_id="https://www.chotot.com/mua-ban-laptop",
        )

        async def _call_tool(tool_name, arguments):
            if tool_name == "x_scrape":
                raise XActionsMcpError("Tool x_scrape not found", code="XACT_404")
            raise XActionsMcpError("Rate limit exceeded", code="XACT_4291", retry_after=45)

        client.call_tool = AsyncMock(side_effect=_call_tool)

        with pytest.raises(XActionsMcpError) as exc_info:
            await adapter.fetch_posts_for_target(target)
        assert exc_info.value.code == "XACT_4291"
        assert exc_info.value.retry_after == 45

    @pytest.mark.asyncio
    async def test_fetch_posts_for_target_primary_non_404_error_reraised(self):
        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        target = FakeTarget(
            platform="chotot_category",
            target_id="https://www.chotot.com/mua-ban-laptop",
        )

        client.call_tool = AsyncMock(
            side_effect=XActionsMcpError("Rate limit", code="XACT_4291", retry_after=30)
        )

        with pytest.raises(XActionsMcpError) as exc_info:
            await adapter.fetch_posts_for_target(target)
        assert exc_info.value.code == "XACT_4291"
        assert client.call_tool.call_count == 1

    @pytest.mark.asyncio
    async def test_ingest_raw_post_to_stream_single_writer_enabled_skips_xadd(
        self, monkeypatch
    ):
        """Defense-in-depth guard: single-writer flag ON bypasses Redis XADD."""
        from app.config import config
        from app.proprietary.platforms.xactions.models import SocialPostData

        monkeypatch.setattr(config, "XACTIONS_STREAM_SINGLE_WRITER_ENABLED", True)

        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        redis_client = MagicMock()
        redis_client.xadd = AsyncMock()

        post = SocialPostData(
            platform="facebook",
            external_post_id="fb_1",
            content="hello",
        )
        result = await adapter.ingest_raw_post_to_stream(post, redis_client=redis_client)

        assert result is None
        redis_client.xadd.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_raw_post_to_stream_single_writer_disabled_calls_xadd(
        self, monkeypatch
    ):
        """Legacy dual-write: flag OFF publishes to stream:social:raw_posts."""
        from app.config import config
        from app.proprietary.platforms.xactions.constants import (
            STREAM_SOCIAL_RAW_POSTS,
        )
        from app.proprietary.platforms.xactions.models import SocialPostData

        monkeypatch.setattr(config, "XACTIONS_STREAM_SINGLE_WRITER_ENABLED", False)

        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        redis_client = MagicMock()
        redis_client.xadd = AsyncMock(return_value="123-0")

        post = SocialPostData(
            platform="facebook",
            external_post_id="fb_1",
            content="hello",
        )
        result = await adapter.ingest_raw_post_to_stream(post, redis_client=redis_client)

        assert result == "123-0"
        redis_client.xadd.assert_called_once()
        call_args = redis_client.xadd.call_args
        assert call_args.args[0] == STREAM_SOCIAL_RAW_POSTS

    @pytest.mark.asyncio
    async def test_ingest_raw_post_to_stream_payload_has_no_none_values(
        self, monkeypatch
    ):
        """Regression test for spec-bugfix-adapter-v2-todict-none-fields:
        payload passed to xadd must not contain None values (Redis rejects with
        ``DataError``). Verify Optional fields omitted or coerced to non-None
        strings, datetimes to ISO strings, collections to JSON strings."""
        import json
        from datetime import UTC, datetime

        from app.config import config
        from app.proprietary.platforms.xactions.constants import (
            STREAM_SOCIAL_RAW_POSTS,
        )
        from app.proprietary.platforms.xactions.models import SocialPostData

        monkeypatch.setattr(config, "XACTIONS_STREAM_SINGLE_WRITER_ENABLED", False)

        client = XActionsMcpClientWithAdmin()
        adapter = XActionsSocialAdapterV2(client=client)
        redis_client = MagicMock()
        redis_client.xadd = AsyncMock(return_value="456-0")

        post = SocialPostData(
            platform="facebook",
            external_post_id="fb_2",
            content="hello world",
            # Many Optional fields default to None — the bug was that to_dict()
            # leaked them into the xadd payload.
            author_id=None,
            category=None,
            client_id=None,
            published_at=datetime(2026, 9, 14, 12, 0, 0, tzinfo=UTC),
            media_urls=["https://example.com/a.jpg", "https://example.com/b.jpg"],
            raw_entities={"emails": ["x@y.z"], "phones": []},
        )
        result = await adapter.ingest_raw_post_to_stream(post, redis_client=redis_client)

        assert result == "456-0"
        redis_client.xadd.assert_called_once()
        call_args = redis_client.xadd.call_args
        assert call_args.args[0] == STREAM_SOCIAL_RAW_POSTS

        payload = call_args.args[1]
        # No None values anywhere — Redis would reject with DataError.
        assert all(v is not None for v in payload.values()), (
            f"payload contains None values: "
            f"{[k for k, v in payload.items() if v is None]}"
        )
        # Optional fields that were None must not appear in payload at all.
        for absent in ("author_id", "category", "client_id"):
            # Either the key is absent OR it was coerced to a non-None string.
            if absent in payload:
                assert payload[absent] is not None
        # Datetimes serialized to ISO-8601 string.
        assert payload["published_at"] == "2026-09-14T12:00:00+00:00"
        # Collections serialized to JSON strings that round-trip.
        assert json.loads(payload["media_urls"]) == [
            "https://example.com/a.jpg",
            "https://example.com/b.jpg",
        ]
        assert json.loads(payload["raw_entities"]) == {
            "emails": ["x@y.z"],
            "phones": [],
        }
        # Schema contract — producer emits schema_version for REQ-X2 contract.
        assert payload.get("schema_version") == "1"


class XActionsMcpClientWithAdmin:
    """Fake client that passes call_tool through."""

    def __init__(self):
        self.admin_token = "admin"
        self._session = MagicMock()
        self._session.call_tool = AsyncMock(
            return_value={
                "success": True,
                "data": [],
                "meta": {},
                "summary": {},
                "artifact_path": None,
            }
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def call_tool(self, tool_name: str, arguments: dict):
        return await self._session.call_tool(tool_name, arguments=arguments)

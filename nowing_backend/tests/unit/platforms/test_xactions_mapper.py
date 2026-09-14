"""Unit tests for UniversalScrapeTargetMapper."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.config import config
from app.proprietary.platforms.xactions.action_matrix import CanonicalActionMatrix
from app.proprietary.platforms.xactions.adapter_v2 import UniversalScrapeTargetMapper
from app.proprietary.platforms.xactions.models import SocialMonitoredTargetData


def _make_target(
    platform: str,
    target_id: str,
    *,
    id: int | None = None,
    workspace_id: int | None = None,
) -> SocialMonitoredTargetData:
    target = SocialMonitoredTargetData(
        platform=platform,
        target_id=target_id,
        target_name="test",
        account_id="acct1",
        proxy_url="http://proxy:8080",
    )
    # SocialMonitoredTargetData doesn't declare id/workspace_id — attach for tests.
    target.id = id
    target.workspace_id = workspace_id
    return target


class TestUniversalScrapeTargetMapper:
    @pytest.mark.parametrize(
        "platform,expected_tool",
        [
            ("facebook_group", "x_facebook_group_posts"),
            ("facebook_page", "x_facebook_posts"),
            ("twitter_keyword", "x_search_tweets"),
            ("twitter_user", "x_get_tweets"),
            ("tiktok_hashtag", "x_scrape"),
            ("chotot_category", "x_scrape"),
            ("shopee_keyword", "x_scrape"),
            ("topcv_search", "x_scrape"),
            ("vietnamworks_search", "x_scrape"),
            ("linkedin_company", "x_scrape"),
            ("batdongsan_category", "x_scrape"),
            ("masothue_lookup", "x_scrape"),
            ("b2b_registry_search", "x_scrape"),
        ],
    )
    def test_platform_to_tool_mapping(self, platform: str, expected_tool: str):
        target = _make_target(platform, "tid")
        tool, _ = UniversalScrapeTargetMapper.map(target)
        assert tool == expected_tool

    def test_facebook_group_args(self):
        target = _make_target("facebook_group", "group123")
        _, args = UniversalScrapeTargetMapper.map(target)
        assert args["url"] == "https://www.facebook.com/groups/group123"
        assert args["limit"] == 20

    def test_facebook_page_args(self):
        target = _make_target("facebook_page", "page456")
        _, args = UniversalScrapeTargetMapper.map(target)
        assert args["url"] == "https://www.facebook.com/page456"

    def test_twitter_keyword_args(self):
        target = _make_target("twitter_keyword", "AI")
        _, args = UniversalScrapeTargetMapper.map(target)
        assert args["query"] == "AI"
        assert args["limit"] == 20

    def test_twitter_user_args(self):
        target = _make_target("twitter_user", "@elon")
        _, args = UniversalScrapeTargetMapper.map(target)
        assert args["username"] == "elon"

    def test_tiktok_hashtag_args(self):
        target = _make_target("tiktok_hashtag", "realestate")
        _, args = UniversalScrapeTargetMapper.map(target)
        assert args == {"platform": "tiktok", "action": "posts", "hashtag": "realestate"}

    def test_masothue_lookup_args(self):
        target = _make_target("masothue_lookup", "0123456789")
        _, args = UniversalScrapeTargetMapper.map(target)
        assert args == {"platform": "masothue", "action": "lookup", "taxCode": "0123456789"}

    def test_unsupported_platform_raises(self):
        target = _make_target("invalid_platform", "x")
        with pytest.raises(ValueError, match="Unsupported social platform"):
            UniversalScrapeTargetMapper.map(target)

    def test_full_url_passthrough(self):
        target = _make_target("facebook_group", "https://www.facebook.com/groups/abc")
        _, args = UniversalScrapeTargetMapper.map(target)
        assert args["url"] == "https://www.facebook.com/groups/abc"


class TestUnifiedDispatchFlagOn:
    """``XACTIONS_USE_UNIFIED_DISPATCH=true`` — matrix-driven x_scrape envelope."""

    @pytest.fixture(autouse=True)
    def _flag_on(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", True)
        CanonicalActionMatrix.reset()
        yield
        CanonicalActionMatrix.reset()

    def test_map_returns_nested_envelope(self):
        target = _make_target("tiktok_hashtag", "realestate", id=42, workspace_id=7)
        tool, args = UniversalScrapeTargetMapper.map(target)
        assert tool == "x_scrape"
        assert args["platform"] == "tiktok"
        assert args["action"] == "posts_by_hashtag"
        assert args["args"] == {"hashtag": "realestate"}
        assert args["context"] == {"targetId": 42, "workspaceId": 7}
        # No flat top-level fields
        assert "hashtag" not in args
        assert "category" not in args

    def test_map_target_id_fallback_to_target_id_attr(self):
        target = _make_target("shopee_keyword", "phone", id=None, workspace_id=None)
        tool, args = UniversalScrapeTargetMapper.map(target)
        assert args["context"]["targetId"] == "phone"  # falls back to target_id
        assert args["context"]["workspaceId"] is None

    def test_map_masothue_canonical_action(self):
        target = _make_target("masothue_lookup", "0123456789")
        tool, args = UniversalScrapeTargetMapper.map(target)
        assert tool == "x_scrape"
        assert args["platform"] == "masothue"
        assert args["action"] == "company_by_taxcode"
        assert args["args"] == {"taxCode": "0123456789"}

    def test_map_linkedin_company(self):
        target = _make_target("linkedin_company", "acme-corp")
        tool, args = UniversalScrapeTargetMapper.map(target)
        assert args["platform"] == "linkedin"
        assert args["action"] == "company_profile"
        assert args["args"] == {"company": "acme-corp"}

    def test_map_legacy_facebook_stays_dedicated(self):
        target = _make_target("facebook_group", "grp123", id=1, workspace_id=2)
        tool, args = UniversalScrapeTargetMapper.map(target)
        # Facebook stays on dedicated tool even when flag is ON
        assert tool == "x_facebook_group_posts"
        assert "url" in args
        assert "args" not in args  # not nested

    def test_map_legacy_twitter_stays_dedicated(self):
        target = _make_target("twitter_keyword", "AI")
        tool, args = UniversalScrapeTargetMapper.map(target)
        assert tool == "x_search_tweets"
        assert args["query"] == "AI"

    def test_map_unsupported_platform_raises(self):
        target = _make_target("xyz_unknown", "x")
        with pytest.raises(ValueError, match="Unsupported social platform"):
            UniversalScrapeTargetMapper.map(target)

    async def test_map_async_flag_on_uses_live_matrix(self):
        # Live catalog returns a custom action not in static fallback
        client = AsyncMock()
        client.call_tool = AsyncMock(
            return_value={
                "actions": [
                    {
                        "platform": "tiktok",
                        "action": "posts_by_hashtag",
                        "requiredArgs": ["hashtag"],
                        "match": {"target_kind": "hashtag"},
                    }
                ]
            }
        )
        target = _make_target("tiktok_hashtag", "trending", id=9, workspace_id=3)
        tool, args = await UniversalScrapeTargetMapper.map_async(target, client)
        assert tool == "x_scrape"
        assert args["action"] == "posts_by_hashtag"
        assert args["args"] == {"hashtag": "trending"}
        client.call_tool.assert_awaited_once_with("x_actions_list", {})

    async def test_map_async_flag_on_falls_back_when_fetch_fails(self):
        client = AsyncMock()
        client.call_tool = AsyncMock(side_effect=RuntimeError("down"))
        target = _make_target("chotot_category", "nha-dat")
        tool, args = await UniversalScrapeTargetMapper.map_async(target, client)
        # Falls back to static matrix
        assert tool == "x_scrape"
        assert args["platform"] == "chotot"
        assert args["action"] == "search_listings"

    async def test_map_async_legacy_tool_delegates_sync(self):
        # Legacy tools don't go through the matrix at all
        client = AsyncMock()
        client.call_tool = AsyncMock(
            side_effect=AssertionError("must not fetch matrix for legacy tools")
        )
        target = _make_target("facebook_page", "page1")
        tool, args = await UniversalScrapeTargetMapper.map_async(target, client)
        assert tool == "x_facebook_posts"
        client.call_tool.assert_not_called()


class TestUnifiedDispatchFlagOff:
    """``XACTIONS_USE_UNIFIED_DISPATCH=false`` — legacy PLATFORM_TOOL_MAP path."""

    @pytest.fixture(autouse=True)
    def _flag_off(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", False)

    def test_map_uses_flat_args(self):
        target = _make_target("tiktok_hashtag", "realestate")
        tool, args = UniversalScrapeTargetMapper.map(target)
        assert tool == "x_scrape"
        # Flag OFF → flat shape (legacy)
        assert args == {
            "platform": "tiktok",
            "action": "posts",
            "hashtag": "realestate",
        }

    async def test_map_async_delegates_to_sync(self):
        target = _make_target("tiktok_hashtag", "realestate")
        tool, args = await UniversalScrapeTargetMapper.map_async(target)
        assert tool == "x_scrape"
        assert args["hashtag"] == "realestate"
        assert "args" not in args  # flat, not nested

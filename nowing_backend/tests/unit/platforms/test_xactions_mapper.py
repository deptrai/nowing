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


class TestLegacyToolDeprecation:
    """Story 36.6b — Route FB/Twitter via Unified x_scrape Dispatch.

    Gated on BOTH XACTIONS_USE_UNIFIED_DISPATCH and XACTIONS_LEGACY_TOOL_DEPRECATION.
    """

    @pytest.mark.parametrize(
        "platform,target_id,expected_tool,expected_args",
        [
            (
                "facebook_group",
                "grp123",
                "x_facebook_group_posts",
                {"url": "https://www.facebook.com/groups/grp123", "limit": 20},
            ),
            (
                "facebook_page",
                "page456",
                "x_facebook_posts",
                {"url": "https://www.facebook.com/page456", "limit": 20},
            ),
            (
                "twitter_keyword",
                "AI agents",
                "x_search_tweets",
                {"query": "AI agents", "limit": 20},
            ),
            (
                "twitter_user",
                "@elon",
                "x_get_tweets",
                {"username": "elon", "limit": 20},
            ),
        ],
    )
    def test_deprecation_flag_alone_is_noop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        platform: str,
        target_id: str,
        expected_tool: str,
        expected_args: dict,
    ):
        """Deprecation ON without unified dispatch still returns legacy tool calls."""
        monkeypatch.setattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", False)
        monkeypatch.setattr(config, "XACTIONS_LEGACY_TOOL_DEPRECATION", True)

        target = _make_target(platform, target_id)
        tool, args = UniversalScrapeTargetMapper.map(target)
        assert tool == expected_tool
        assert args == expected_args

    def test_unified_on_deprecation_off_preserves_legacy_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Unified ON with deprecation OFF leaves FB and Twitter on dedicated tools."""
        monkeypatch.setattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", True)
        monkeypatch.setattr(config, "XACTIONS_LEGACY_TOOL_DEPRECATION", False)
        CanonicalActionMatrix.reset()

        for platform, expected_tool in [
            ("facebook_group", "x_facebook_group_posts"),
            ("facebook_page", "x_facebook_posts"),
            ("twitter_keyword", "x_search_tweets"),
            ("twitter_user", "x_get_tweets"),
        ]:
            target = _make_target(platform, "test_target")
            tool, _ = UniversalScrapeTargetMapper.map(target)
            assert tool == expected_tool

    @pytest.mark.parametrize(
        "platform,target_id,expected_tool",
        [
            ("facebook_group", "grp", "x_facebook_group_posts"),
            ("facebook_page", "page", "x_facebook_posts"),
            ("twitter_keyword", "q", "x_search_tweets"),
            ("twitter_user", "@u", "x_get_tweets"),
        ],
    )
    async def test_map_async_deprecation_alone_is_noop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        platform: str,
        target_id: str,
        expected_tool: str,
    ):
        """Deprecation flag alone (unified OFF) — map_async must not bypass legacy."""
        monkeypatch.setattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", False)
        monkeypatch.setattr(config, "XACTIONS_LEGACY_TOOL_DEPRECATION", True)

        target = _make_target(platform, target_id)
        tool, _ = await UniversalScrapeTargetMapper.map_async(target)
        assert tool == expected_tool

    @pytest.mark.parametrize(
        "platform,expected_tool",
        [
            ("facebook_group", "x_facebook_group_posts"),
            ("facebook_page", "x_facebook_posts"),
            ("twitter_keyword", "x_search_tweets"),
            ("twitter_user", "x_get_tweets"),
        ],
    )
    async def test_map_async_unified_on_deprecation_off_preserves_legacy(
        self,
        monkeypatch: pytest.MonkeyPatch,
        platform: str,
        expected_tool: str,
    ):
        """Unified ON + deprecation OFF — map_async still uses dedicated tools."""
        monkeypatch.setattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", True)
        monkeypatch.setattr(config, "XACTIONS_LEGACY_TOOL_DEPRECATION", False)
        CanonicalActionMatrix.reset()

        target = _make_target(platform, "q")
        tool, _ = await UniversalScrapeTargetMapper.map_async(target)
        assert tool == expected_tool

    class TestBothFlagsOn:
        @pytest.fixture(autouse=True)
        def _setup_flags(self, monkeypatch: pytest.MonkeyPatch):
            monkeypatch.setattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", True)
            monkeypatch.setattr(config, "XACTIONS_LEGACY_TOOL_DEPRECATION", True)
            CanonicalActionMatrix.reset()
            yield
            CanonicalActionMatrix.reset()

        def test_facebook_group_urlified(self):
            target = _make_target("facebook_group", "group123", id=10, workspace_id=20)
            tool, args = UniversalScrapeTargetMapper.map(target)
            assert tool == "x_scrape"
            assert args["platform"] == "facebook"
            assert args["action"] == "group_posts"
            assert args["args"] == {"url": "https://www.facebook.com/groups/group123", "limit": 20}
            assert args["context"] == {"targetId": 10, "workspaceId": 20}

        def test_facebook_group_full_url_passthrough(self):
            url = "https://www.facebook.com/groups/abc"
            target = _make_target("facebook_group", url, id=10, workspace_id=20)
            tool, args = UniversalScrapeTargetMapper.map(target)
            assert tool == "x_scrape"
            assert args["platform"] == "facebook"
            assert args["action"] == "group_posts"
            assert args["args"] == {"url": url, "limit": 20}

        def test_facebook_page_urlified(self):
            target = _make_target("facebook_page", "page456", id=11, workspace_id=21)
            tool, args = UniversalScrapeTargetMapper.map(target)
            assert tool == "x_scrape"
            assert args["platform"] == "facebook"
            assert args["action"] == "page_posts"
            assert args["args"] == {"url": "https://www.facebook.com/page456", "limit": 20}
            assert args["context"] == {"targetId": 11, "workspaceId": 21}

        def test_facebook_page_full_url_passthrough(self):
            url = "https://www.facebook.com/page456"
            target = _make_target("facebook_page", url, id=11, workspace_id=21)
            tool, args = UniversalScrapeTargetMapper.map(target)
            assert tool == "x_scrape"
            assert args["platform"] == "facebook"
            assert args["action"] == "page_posts"
            assert args["args"] == {"url": url, "limit": 20}

        def test_twitter_keyword(self):
            target = _make_target("twitter_keyword", "AI agents", id=12, workspace_id=22)
            tool, args = UniversalScrapeTargetMapper.map(target)
            assert tool == "x_scrape"
            assert args["platform"] == "twitter"
            assert args["action"] == "search_tweets"
            assert args["args"] == {"query": "AI agents", "limit": 20}
            assert args["context"] == {"targetId": 12, "workspaceId": 22}

        def test_twitter_user_strips_at_symbol(self):
            target = _make_target("twitter_user", "@elon", id=13, workspace_id=23)
            tool, args = UniversalScrapeTargetMapper.map(target)
            assert tool == "x_scrape"
            assert args["platform"] == "twitter"
            assert args["action"] == "user_tweets"
            assert args["args"] == {"username": "elon", "limit": 20}
            assert args["context"] == {"targetId": 13, "workspaceId": 23}

        def test_twitter_user_without_at_symbol(self):
            target = _make_target("twitter_user", "elon", id=13, workspace_id=23)
            tool, args = UniversalScrapeTargetMapper.map(target)
            assert tool == "x_scrape"
            assert args["args"] == {"username": "elon", "limit": 20}

        def test_empty_target_id_raises_value_error(self):
            target = _make_target("facebook_group", "")
            with pytest.raises(ValueError, match="target_id required for action group_posts"):
                UniversalScrapeTargetMapper.map(target)

            target_none = _make_target("facebook_group", None)  # type: ignore[arg-type]
            with pytest.raises(ValueError, match="target_id required for action group_posts"):
                UniversalScrapeTargetMapper.map(target_none)

        async def test_map_async_with_both_flags_on(self):
            client = AsyncMock()
            client.call_tool = AsyncMock(
                return_value={
                    "actions": [
                        {
                            "platform": "facebook",
                            "action": "group_posts",
                            "requiredArgs": ["url"],
                            "optionalArgs": ["limit"],
                            "match": {"target_kind": "group"},
                        }
                    ]
                }
            )
            target = _make_target("facebook_group", "group99", id=5, workspace_id=6)
            tool, args = await UniversalScrapeTargetMapper.map_async(target, client)
            assert tool == "x_scrape"
            assert args["platform"] == "facebook"
            assert args["action"] == "group_posts"
            assert args["args"] == {"url": "https://www.facebook.com/groups/group99", "limit": 20}
            client.call_tool.assert_awaited_once_with("x_actions_list", {})

        async def test_map_async_partial_catalog_merges_static_fallback(self):
            # Live catalog returns only tiktok, lacking facebook/twitter
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
            target = _make_target("twitter_user", "@jack", id=1, workspace_id=2)
            tool, args = await UniversalScrapeTargetMapper.map_async(target, client)
            assert tool == "x_scrape"
            assert args["platform"] == "twitter"
            assert args["action"] == "user_tweets"
            assert args["args"] == {"username": "jack", "limit": 20}

        async def test_map_async_default_client_none_uses_static_fallback(self):
            """map_async(target) without explicit client → STATIC_FALLBACK_MATRIX path."""
            target = _make_target("facebook_group", "grp_none", id=9, workspace_id=11)
            tool, args = await UniversalScrapeTargetMapper.map_async(target)
            assert tool == "x_scrape"
            assert args["platform"] == "facebook"
            assert args["action"] == "group_posts"
            assert args["args"] == {
                "url": "https://www.facebook.com/groups/grp_none",
                "limit": 20,
            }
            assert args["context"] == {"targetId": 9, "workspaceId": 11}

        def test_whitespace_target_id_raises_value_error(self):
            target = _make_target("facebook_group", "   ")
            with pytest.raises(ValueError, match="target_id required for action group_posts"):
                UniversalScrapeTargetMapper.map(target)

        def test_twitter_user_all_at_signs_rejected(self):
            target = _make_target("twitter_user", "@@@")
            with pytest.raises(ValueError, match="target_id required for action"):
                UniversalScrapeTargetMapper.map(target)

        def test_non_string_target_id_coerced(self):
            target = _make_target("twitter_user", 12345, id=1, workspace_id=2)  # type: ignore[arg-type]
            tool, args = UniversalScrapeTargetMapper.map(target)
            assert tool == "x_scrape"
            assert args["args"]["username"] == "12345"

        def test_multi_required_args_descriptor_raises(self):
            """Descriptor with 2+ requiredArgs must fail loudly, not guess binding."""
            from app.proprietary.platforms.xactions.adapter_v2 import _build_unified_args
            descriptor = {"requiredArgs": ["url", "format"], "optionalArgs": []}
            with pytest.raises(ValueError, match="requires multiple args"):
                _build_unified_args("facebook_group", "abc", descriptor, "group_posts")

        @pytest.mark.parametrize(
            "platform_kind,target_id,expected_action,arg_name,arg_value",
            [
                ("facebook_page", "page99", "page_posts", "url", "https://www.facebook.com/page99"),
                ("twitter_keyword", "ai agents", "search_tweets", "query", "ai agents"),
                ("twitter_user", "@jack", "user_tweets", "username", "jack"),
            ],
        )
        async def test_map_async_other_legacy_kinds(
            self, platform_kind, target_id, expected_action, arg_name, arg_value
        ):
            client = AsyncMock()
            client.call_tool = AsyncMock(
                return_value={
                    "actions": [
                        {
                            "platform": platform_kind.split("_")[0],
                            "action": expected_action,
                            "requiredArgs": [arg_name],
                            "optionalArgs": ["limit"],
                            "match": {"target_kind": platform_kind.split("_", 1)[1]},
                        }
                    ]
                }
            )
            target = _make_target(platform_kind, target_id, id=7, workspace_id=8)
            tool, args = await UniversalScrapeTargetMapper.map_async(target, client)
            assert tool == "x_scrape"
            assert args["action"] == expected_action
            assert args["args"][arg_name] == arg_value

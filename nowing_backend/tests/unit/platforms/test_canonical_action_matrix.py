"""Unit tests for CanonicalActionMatrix (Story 36.6a)."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.proprietary.platforms.xactions.action_matrix import (
    STATIC_FALLBACK_MATRIX,
    ActionDescriptor,
    CanonicalActionMatrix,
    derive_platform_action,
    parse_action_descriptors,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_matrix_cache() -> None:
    CanonicalActionMatrix.reset()
    yield
    CanonicalActionMatrix.reset()


def _client_returning(actions: list[dict[str, Any]]) -> Any:
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value={"actions": actions})
    return client


class TestParseActionDescriptors:
    def test_parse_list_envelope(self):
        raw = {
            "actions": [
                {"platform": "tiktok", "action": "posts_by_hashtag", "requiredArgs": ["hashtag"]},
                {"platform": "tiktok", "action": "user_posts", "requiredArgs": ["username"]},
                {"platform": "shopee", "action": "search_products", "requiredArgs": ["keyword"]},
            ]
        }
        matrix = parse_action_descriptors(raw)
        assert set(matrix.keys()) == {"tiktok", "shopee"}
        assert "posts_by_hashtag" in matrix["tiktok"]
        assert matrix["tiktok"]["posts_by_hashtag"]["requiredArgs"] == ["hashtag"]

    def test_parse_plain_list(self):
        raw = [
            {"platform": "tiktok", "action": "posts_by_hashtag", "requiredArgs": ["hashtag"]},
        ]
        matrix = parse_action_descriptors(raw)
        assert "tiktok" in matrix

    def test_parse_skips_malformed(self):
        raw = {
            "actions": [
                {"platform": "tiktok", "action": "posts_by_hashtag"},
                {"bogus": "entry"},  # missing required fields → skipped
            ]
        }
        matrix = parse_action_descriptors(raw)
        assert "tiktok" in matrix
        assert len(matrix["tiktok"]) == 1

    def test_parse_none_and_empty(self):
        assert parse_action_descriptors(None) == {}
        assert parse_action_descriptors({}) == {}
        assert parse_action_descriptors([]) == {}
        assert parse_action_descriptors("not a list") == {}

    def test_parse_platform_keyed_dict(self):
        raw = {
            "tiktok": {"posts_by_hashtag": {"requiredArgs": ["hashtag"]}},
        }
        matrix = parse_action_descriptors(raw)
        assert matrix["tiktok"]["posts_by_hashtag"]["requiredArgs"] == ["hashtag"]


class TestDerivePlatformAction:
    MATRIX = {
        "tiktok": {
            "posts_by_hashtag": {
                "requiredArgs": ["hashtag"],
                "match": {"target_kind": "hashtag"},
            },
            "user_posts": {
                "requiredArgs": ["username"],
                "match": {"target_kind": "user"},
            },
        },
        "shopee": {
            "search_products": {
                "requiredArgs": ["keyword"],
                "match": {"target_kind": "keyword"},
            },
        },
    }

    def test_compound_kind_resolves_matched_action(self):
        platform, action = derive_platform_action("tiktok_hashtag", self.MATRIX)
        assert (platform, action) == ("tiktok", "posts_by_hashtag")

    def test_compound_kind_second_action(self):
        platform, action = derive_platform_action("tiktok_user", self.MATRIX)
        assert (platform, action) == ("tiktok", "user_posts")

    def test_bare_platform_single_action(self):
        platform, action = derive_platform_action("shopee", self.MATRIX)
        assert (platform, action) == ("shopee", "search_products")

    def test_bare_platform_ambiguous_raises(self):
        with pytest.raises(ValueError, match="Ambiguous action for platform tiktok"):
            derive_platform_action("tiktok", self.MATRIX)

    def test_unknown_platform_raises(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            derive_platform_action("xyz_unknown", self.MATRIX)

    def test_unknown_kind_multi_action_raises(self):
        with pytest.raises(ValueError, match="Unsupported action kind"):
            derive_platform_action("tiktok_bogus", self.MATRIX)

    def test_empty_platform_kind_raises(self):
        with pytest.raises(ValueError, match="platform_kind is required"):
            derive_platform_action("", self.MATRIX)

    @pytest.mark.parametrize(
        "platform_kind,expected_platform,expected_action",
        [
            ("facebook_group", "facebook", "group_posts"),
            ("facebook_page", "facebook", "page_posts"),
            ("twitter_keyword", "twitter", "search_tweets"),
            ("twitter_user", "twitter", "user_tweets"),
        ],
    )
    def test_legacy_platform_kinds_derive_against_static_fallback(
        self, platform_kind: str, expected_platform: str, expected_action: str
    ):
        platform, action = derive_platform_action(platform_kind, STATIC_FALLBACK_MATRIX)
        assert (platform, action) == (expected_platform, expected_action)

    def test_static_fallback_matrix_legacy_descriptors(self):
        fb_group = STATIC_FALLBACK_MATRIX["facebook"]["group_posts"]
        assert fb_group["requiredArgs"] == ["url"]
        assert fb_group["optionalArgs"] == ["limit"]
        assert fb_group["match"]["target_kind"] == "group"

        fb_page = STATIC_FALLBACK_MATRIX["facebook"]["page_posts"]
        assert fb_page["requiredArgs"] == ["url"]
        assert fb_page["optionalArgs"] == ["limit"]
        assert fb_page["match"]["target_kind"] == "page"

        tw_keyword = STATIC_FALLBACK_MATRIX["twitter"]["search_tweets"]
        assert tw_keyword["requiredArgs"] == ["query"]
        assert tw_keyword["optionalArgs"] == ["limit"]
        assert tw_keyword["match"]["target_kind"] == "keyword"

        tw_user = STATIC_FALLBACK_MATRIX["twitter"]["user_tweets"]
        assert tw_user["requiredArgs"] == ["username"]
        assert tw_user["optionalArgs"] == ["limit"]
        assert tw_user["match"]["target_kind"] == "user"


class TestCanonicalActionMatrixCache:
    async def test_get_fetches_and_caches(self):
        client = _client_returning(
            [{"platform": "tiktok", "action": "posts_by_hashtag", "requiredArgs": ["hashtag"]}]
        )
        matrix = await CanonicalActionMatrix.get(client)
        assert "tiktok" in matrix
        client.call_tool.assert_awaited_once_with("x_actions_list", {})

        # Second call within TTL → no refetch
        matrix2 = await CanonicalActionMatrix.get(client)
        assert matrix2 is matrix
        assert client.call_tool.await_count == 1

    async def test_get_stale_refetches(self):
        client = _client_returning(
            [{"platform": "tiktok", "action": "posts_by_hashtag"}]
        )
        await CanonicalActionMatrix.get(client)
        # Force expiry
        CanonicalActionMatrix._cache_timestamp = time.monotonic() - 400
        await CanonicalActionMatrix.get(client)
        assert client.call_tool.await_count == 2

    async def test_get_fetch_failure_falls_back_to_static(self):
        client = AsyncMock()
        client.call_tool = AsyncMock(side_effect=RuntimeError("XActions down"))
        matrix = await CanonicalActionMatrix.get(client)
        assert matrix == STATIC_FALLBACK_MATRIX

    async def test_get_empty_catalog_falls_back_to_static(self):
        client = _client_returning([])
        matrix = await CanonicalActionMatrix.get(client)
        assert matrix == STATIC_FALLBACK_MATRIX

    async def test_get_partial_catalog_merges_with_static(self):
        # Live returns only 1 platform; static should fill the rest
        client = _client_returning(
            [{"platform": "tiktok", "action": "posts_by_hashtag", "requiredArgs": ["hashtag"]}]
        )
        matrix = await CanonicalActionMatrix.get(client)
        # Live platform present
        assert "tiktok" in matrix
        # Static-only platforms still available via merge
        assert "shopee" in matrix
        assert "masothue" in matrix
        assert "b2b_registry" in matrix

    async def test_get_client_none_returns_fallback(self):
        matrix = await CanonicalActionMatrix.get(None)
        assert matrix == STATIC_FALLBACK_MATRIX

    async def test_get_live_descriptor_inherits_static_match(self):
        # Live descriptor without `match` should inherit from static
        client = _client_returning(
            [
                {
                    "platform": "tiktok",
                    "action": "posts_by_hashtag",
                    "requiredArgs": ["hashtag"],
                    # no match hint
                }
            ]
        )
        matrix = await CanonicalActionMatrix.get(client)
        assert matrix["tiktok"]["posts_by_hashtag"]["match"]["target_kind"] == "hashtag"


class TestGetSync:
    def test_get_sync_returns_fallback_when_cache_cold(self):
        matrix = CanonicalActionMatrix.get_sync()
        assert matrix == STATIC_FALLBACK_MATRIX

    async def test_get_sync_returns_cache_when_fresh(self):
        client = _client_returning(
            [{"platform": "tiktok", "action": "posts_by_hashtag", "requiredArgs": ["hashtag"]}]
        )
        live_matrix = await CanonicalActionMatrix.get(client)
        sync_matrix = CanonicalActionMatrix.get_sync()
        assert sync_matrix is live_matrix

    async def test_get_sync_falls_back_when_cache_stale(self):
        client = _client_returning(
            [{"platform": "tiktok", "action": "posts_by_hashtag"}]
        )
        await CanonicalActionMatrix.get(client)
        CanonicalActionMatrix._cache_timestamp = time.monotonic() - 400
        sync_matrix = CanonicalActionMatrix.get_sync()
        assert sync_matrix == STATIC_FALLBACK_MATRIX


class TestActionDescriptor:
    def test_defaults(self):
        desc = ActionDescriptor(platform="tiktok", action="posts_by_hashtag")
        assert desc.requiredArgs == []
        assert desc.optionalArgs == []
        assert desc.match == {}

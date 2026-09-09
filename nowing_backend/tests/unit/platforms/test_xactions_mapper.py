"""Unit tests for UniversalScrapeTargetMapper."""
from __future__ import annotations

import pytest

from app.proprietary.platforms.xactions.adapter_v2 import UniversalScrapeTargetMapper
from app.proprietary.platforms.xactions.models import SocialMonitoredTargetData


def _make_target(platform: str, target_id: str) -> SocialMonitoredTargetData:
    return SocialMonitoredTargetData(
        platform=platform,
        target_id=target_id,
        target_name="test",
        account_id="acct1",
        proxy_url="http://proxy:8080",
    )


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

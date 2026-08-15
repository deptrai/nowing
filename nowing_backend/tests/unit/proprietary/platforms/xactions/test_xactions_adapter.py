"""Unit tests for XActionsSocialAdapter."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.proprietary.platforms.xactions.adapter import (
    SocialPostData,
    XActionsSocialAdapter,
)


class TestXActionsSocialAdapter:
    """Test suite for XActions social ingress adapter."""

    @pytest.fixture
    def adapter(self):
        return XActionsSocialAdapter(
            xactions_path="/Users/luisphan/Documents/GitHub/XActions",
            proxy_url="socks5://user:pass@1.2.3.4:1080",
        )

    def test_sticky_proxy_binding(self):
        """AD-SOC-3: 1-to-1 sticky proxy binding per account/target."""
        adapter = XActionsSocialAdapter()
        adapter.bind_account_proxy(account_id="fb_acc_01", proxy_url="socks5://proxy1.internal:1080")
        adapter.bind_account_proxy(account_id="fb_acc_02", proxy_url="socks5://proxy2.internal:1080")

        assert adapter.get_account_proxy("fb_acc_01") == "socks5://proxy1.internal:1080"
        assert adapter.get_account_proxy("fb_acc_02") == "socks5://proxy2.internal:1080"
        assert adapter.get_account_proxy("unknown") is None

    @pytest.mark.asyncio
    async def test_fetch_facebook_group_posts_mapped(self, adapter):
        """AD-SOC-1 & AD-SOC-6: Parse Facebook group raw response to standard SocialPostData."""
        raw_fb_posts = [
            {
                "id": "post_1001",
                "text": "Bán gấp nhà Cầu Giấy 5 tỷ LH 0912345678",
                "author": {"id": "usr_99", "name": "Nguyễn Văn A"},
                "created_time": "2026-08-15T08:30:00Z",
                "reactions_count": 15,
                "comments_count": 4,
                "shares_count": 1,
                "url": "https://facebook.com/groups/bds/posts/1001",
            }
        ]

        with patch.object(adapter, "_execute_xactions_command", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"success": True, "data": raw_fb_posts}

            posts = await adapter.fetch_facebook_group_posts(group_id="bds_hanoi_group", limit=10)
            assert len(posts) == 1
            post = posts[0]
            assert isinstance(post, SocialPostData)
            assert post.platform == "facebook"
            assert post.external_post_id == "post_1001"
            assert post.author_name == "Nguyễn Văn A"
            assert "0912345678" in post.content
            assert post.reactions_count == 15
            assert post.comments_count == 4

    @pytest.mark.asyncio
    async def test_search_tweets_mapped(self, adapter):
        """AD-SOC-1: Parse Twitter search tweets to SocialPostData."""
        raw_tweets = [
            {
                "id_str": "tweet_8888",
                "full_text": "Tìm kiếm cơ hội đầu tư BĐS ven đô #batdongsan lh o901234567",
                "user": {"id_str": "tw_usr_1", "name": "InvestorVN", "screen_name": "investor_vn"},
                "created_at": "Sat Aug 15 09:00:00 +0000 2026",
                "favorite_count": 30,
                "reply_count": 5,
                "retweet_count": 2,
            }
        ]

        with patch.object(adapter, "_execute_xactions_command", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"success": True, "data": raw_tweets}

            posts = await adapter.search_tweets(query="batdongsan", limit=10)
            assert len(posts) == 1
            post = posts[0]
            assert post.platform == "twitter"
            assert post.external_post_id == "tweet_8888"
            assert post.author_name == "InvestorVN"
            assert post.reactions_count == 30

    @pytest.mark.asyncio
    async def test_ingest_raw_post_to_redis_stream(self, adapter):
        """AD-SOC-4: Push ingested post to Redis Stream 'stream:social:raw_posts'."""
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1723712345678-0")

        post_data = SocialPostData(
            platform="facebook",
            external_post_id="post_999",
            author_id="usr_1",
            author_name="Test User",
            content="Cần bán đất thổ cư",
            post_url="https://facebook.com/123",
            reactions_count=10,
            comments_count=2,
            shares_count=0,
            published_at=datetime.now(UTC),
        )

        msg_id = await adapter.ingest_raw_post_to_stream(post_data, redis_client=mock_redis)
        assert msg_id == "1723712345678-0"
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "stream:social:raw_posts"
        fields = call_args[0][1]
        assert fields["platform"] == "facebook"
        assert fields["external_post_id"] == "post_999"

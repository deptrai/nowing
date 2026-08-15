"""Unit tests for social.search_leads capability & social_search_posts (Story 21.8 / AC 5)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.capabilities.social.search_leads import (
    SOCIAL_SEARCH_LEADS,
    SocialSearchLeadsInput,
    SocialSearchLeadsOutput,
    social_search_posts,
)


class MockPost:
    def __init__(self, platform, external_post_id, content, intent_tag, fit_score, phones, author_name="User"):
        self.platform = platform
        self.external_post_id = external_post_id
        self.content = content
        self.intent_tag = intent_tag
        self.fit_score = fit_score
        self.author_name = author_name
        self.author_url = None
        self.post_url = f"https://{platform}.com/{external_post_id}"
        self.reactions_count = 10
        self.comments_count = 2
        self.shares_count = 1
        self.raw_entities = {"phones": phones, "emails": [], "prices": [], "locations": []}
        self.published_at = None


@pytest.mark.asyncio
async def test_social_search_leads_capability_execution():
    """Verify execution of social.search_leads capability returns filtered items."""
    mock_post_1 = MockPost("facebook", "fb_01", "Bán nhà 0912345678", "sell", 0.85, ["0912345678"])
    mock_post_2 = MockPost("twitter", "tw_02", "Tuyển dụng bds", "hiring", 0.70, [])

    mock_db_session = AsyncMock()
    mock_scalars = AsyncMock()
    mock_scalars.all = lambda: [mock_post_1, mock_post_2]
    mock_result = AsyncMock()
    mock_result.scalars = lambda: mock_scalars
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    mock_session_maker = AsyncMock()
    mock_session_maker.__aenter__.return_value = mock_db_session
    mock_session_maker.__aexit__.return_value = None

    with patch("app.capabilities.social.search_leads.executor.async_session_maker", return_value=mock_session_maker):
        payload = SocialSearchLeadsInput(keyword="bds", limit=10)
        output: SocialSearchLeadsOutput = await SOCIAL_SEARCH_LEADS.executor(payload)

        assert output.total == 2
        assert len(output.items) == 2
        assert output.items[0].platform == "facebook"
        assert output.items[0].phones == ["0912345678"]
        assert output.cost_micros == 4000
        assert not output.degraded


@pytest.mark.asyncio
async def test_social_search_posts_helper():
    """Verify helper function social_search_posts returns list of dicts."""
    mock_post = MockPost("facebook", "fb_99", "Cần bán căn hộ 0987654321", "sell", 0.9, ["0987654321"])

    mock_db_session = AsyncMock()
    mock_scalars = AsyncMock()
    mock_scalars.all = lambda: [mock_post]
    mock_result = AsyncMock()
    mock_result.scalars = lambda: mock_scalars
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    mock_session_maker = AsyncMock()
    mock_session_maker.__aenter__.return_value = mock_db_session
    mock_session_maker.__aexit__.return_value = None

    with patch("app.capabilities.social.search_leads.executor.async_session_maker", return_value=mock_session_maker):
        leads = await social_search_posts(intent="sell", limit=5)
        assert len(leads) == 1
        assert leads[0]["platform"] == "facebook"
        assert leads[0]["external_post_id"] == "fb_99"
        assert "0987654321" in leads[0]["phones"]

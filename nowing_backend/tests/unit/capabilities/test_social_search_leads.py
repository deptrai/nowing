"""Unit tests for social.search_leads capability & social_search_posts (Story 21.8 / AC 5)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.capabilities.core.types import CapabilityContext
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


@pytest.fixture
def mock_db_session_factory():
    """Build a mocked DB session that returns two placeholder social posts."""

    def _factory(posts):
        mock_db_session = AsyncMock()

        def _build_result(stmt):
            # The executor calls session.execute for the SELECT and
            # session.scalar for the COUNT. Return a MagicMock for the SELECT
            # so scalars()/all() are plain sync calls, and a count for scalar.
            stmt_str = str(stmt)
            is_count = "count(" in stmt_str

            if is_count:
                # scalar() should return an int; AsyncMock side_effect does that.
                return len(posts)

            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = posts
            mock_result.scalars.return_value = mock_scalars
            return mock_result

        mock_db_session.execute = AsyncMock(side_effect=_build_result)
        mock_db_session.scalar = AsyncMock(side_effect=_build_result)
        return mock_db_session

    return _factory


@pytest.mark.asyncio
async def test_social_search_leads_capability_execution(mock_db_session_factory):
    """Verify execution of social.search_leads capability returns filtered items."""
    mock_post_1 = MockPost("facebook", "fb_01", "Bán nhà 0912345678", "sell", 0.85, ["0912345678"])
    mock_post_2 = MockPost("twitter", "tw_02", "Tuyển dụng bds", "hiring", 0.70, [])

    mock_db_session = mock_db_session_factory([mock_post_1, mock_post_2])
    ctx = CapabilityContext(session=mock_db_session, workspace_id=1)

    payload = SocialSearchLeadsInput(keyword="bds", limit=10)
    output: SocialSearchLeadsOutput = await SOCIAL_SEARCH_LEADS.executor(payload, ctx)

    assert output.total == 2
    assert len(output.items) == 2
    assert output.items[0].platform == "facebook"
    assert output.items[0].phones == ["0912345678"]
    assert output.cost_micros == 4000
    assert not output.degraded

    # Validate the generated SQL carries the workspace filter and a limit.
    assert mock_db_session.execute.call_count == 1
    executed_stmt = mock_db_session.execute.call_args.args[0]
    stmt_str = str(executed_stmt)
    assert "workspace_id" in stmt_str
    assert "LIMIT" in stmt_str


@pytest.mark.asyncio
async def test_social_search_leads_uses_offset(mock_db_session_factory):
    """Pagination offset is applied to the query."""
    mock_post = MockPost("facebook", "fb_03", "Bán đất", "sell", 0.5, [])
    mock_db_session = mock_db_session_factory([mock_post])
    ctx = CapabilityContext(session=mock_db_session, workspace_id=1)

    payload = SocialSearchLeadsInput(keyword="đất", limit=5, offset=10)
    output = await SOCIAL_SEARCH_LEADS.executor(payload, ctx)

    assert not output.degraded
    assert mock_db_session.execute.call_count == 1
    stmt_str = str(mock_db_session.execute.call_args.args[0])
    assert "OFFSET" in stmt_str


@pytest.mark.asyncio
async def test_social_search_posts_helper(mock_db_session_factory):
    """Verify helper function social_search_posts returns list of dicts."""
    mock_post = MockPost("facebook", "fb_99", "Cần bán căn hộ 0987654321", "sell", 0.9, ["0987654321"])

    mock_db_session = mock_db_session_factory([mock_post])
    ctx = CapabilityContext(session=mock_db_session, workspace_id=1)

    leads = await social_search_posts(intent="sell", limit=5, ctx=ctx)
    assert len(leads) == 1
    assert leads[0]["platform"] == "facebook"
    assert leads[0]["external_post_id"] == "fb_99"
    assert "0987654321" in leads[0]["phones"]

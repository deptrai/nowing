"""Unit tests for XActions Meta-Tool Gateway (Solution 3)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway import (
    _handle_xactions_crawl_post,
    _handle_xactions_scrape,
    _handle_xactions_search,
    create_xactions_meta_tools,
)


@pytest.mark.asyncio
async def test_create_xactions_meta_tools_structure():
    """Verify create_xactions_meta_tools returns 3 expected StructuredTools."""
    tools = create_xactions_meta_tools(
        connector_id=10,
        connector_name="XActions",
        server_config={"url": "http://test:3001/mcp"},
    )
    assert len(tools) == 3
    tool_names = {t.name for t in tools}
    assert tool_names == {"x_search", "x_scrape", "x_crawl_post"}
    for t in tools:
        assert t.metadata["hitl"] is False
        assert t.metadata["mcp_transport"] == "http"


@pytest.mark.asyncio
async def test_search_tweets_dispatch():
    """Verify x_search for twitter dispatches to x_search_tweets."""
    with patch(
        "app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway._execute_xactions_tool",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = {
            "success": True,
            "data": [{"id": "1", "text": "hello twitter"}],
        }

        res_str = await _handle_xactions_search(
            server_config={"url": "http://test:3001/mcp"},
            query="ai agent",
            platform="twitter",
            limit=10,
        )

        mock_exec.assert_called_once_with(
            {"url": "http://test:3001/mcp"},
            "x_search_tweets",
            {"query": "ai agent", "platform": "twitter", "limit": 10},
        )
        parsed = json.loads(res_str)
        assert len(parsed["data"]) == 1
        assert parsed["data"][0]["text"] == "hello twitter"


@pytest.mark.asyncio
async def test_scrape_marketplace_dispatch():
    """Verify x_scrape for facebook marketplace dispatches to x_facebook_marketplace."""
    with patch(
        "app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway._execute_xactions_tool",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = {
            "success": True,
            "data": [{"title": "Honda SH", "price": 50000000}],
        }

        res_str = await _handle_xactions_scrape(
            server_config={"url": "http://test:3001/mcp"},
            platform="facebook",
            action="marketplace",
            query="xe máy",
            location="Ho Chi Minh",
            min_price=10000000,
            limit=5,
        )

        mock_exec.assert_called_once_with(
            {"url": "http://test:3001/mcp"},
            "x_facebook_marketplace",
            {
                "query": "xe máy",
                "limit": 5,
                "dryRun": False,
                "location": "Ho Chi Minh",
                "minPrice": 10000000,
            },
        )
        parsed = json.loads(res_str)
        assert parsed["data"][0]["title"] == "Honda SH"


@pytest.mark.asyncio
async def test_crawl_post_dispatch():
    """Verify x_crawl_post dispatches to x_crawl_post on XActions."""
    with patch(
        "app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway._execute_xactions_tool",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = {
            "success": True,
            "data": [{"id": "post_123", "content": "detailed post content"}],
        }

        res_str = await _handle_xactions_crawl_post(
            server_config={"url": "http://test:3001/mcp"},
            url="https://facebook.com/post/123",
            limit=20,
        )

        mock_exec.assert_called_once_with(
            {"url": "http://test:3001/mcp"},
            "x_crawl_post",
            {
                "platform": "facebook",
                "limit": 20,
                "url": "https://facebook.com/post/123",
            },
        )
        parsed = json.loads(res_str)
        assert parsed["data"][0]["content"] == "detailed post content"


@pytest.mark.asyncio
async def test_search_facebook_default_search_type():
    """Facebook search without search_type defaults to 'posts'."""
    with patch(
        "app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway._execute_xactions_tool",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = {"success": True, "data": []}

        await _handle_xactions_search(
            server_config={"url": "http://test:3001/mcp"},
            query="honda",
            platform="facebook",
        )

        _, _, args = mock_exec.call_args[0]
        assert args["type"] == "posts"


@pytest.mark.asyncio
async def test_scrape_non_twitter_posts_uses_x_scrape():
    """Shopee/TikTok/Chotot 'posts' action must route to x_scrape."""
    with patch(
        "app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway._execute_xactions_tool",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = {"success": True, "data": []}

        await _handle_xactions_scrape(
            server_config={"url": "http://test:3001/mcp"},
            platform="shopee",
            action="posts",
            target="laptop",
            limit=10,
        )

        tool = mock_exec.call_args[0][1]
        assert tool == "x_scrape"


@pytest.mark.asyncio
async def test_format_result_error_without_error_key():
    """A failed result with only 'message' still surfaces the failure."""
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway import (
        _format_result,
    )
    result = {"success": False, "message": "something went wrong"}
    formatted = _format_result("x_test", result)
    assert formatted.startswith("Error")
    assert "something went wrong" in formatted


@pytest.mark.asyncio
async def test_crawl_post_requires_url_or_post_id():
    """x_crawl_post returns an error if both url and post_id are missing."""
    res = await _handle_xactions_crawl_post(
        server_config={"url": "http://test:3001/mcp"},
    )
    assert res.startswith("Error")


@pytest.mark.asyncio
async def test_execute_xactions_tool_calls_client():
    """_execute_xactions_tool builds correct args and passes them to XActionsMcpClient."""
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway import (
        _execute_xactions_tool,
    )

    with patch(
        "app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway.XActionsMcpClient",
        autospec=True,
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.__aenter__.return_value = mock_client
        mock_client.call_tool = AsyncMock(return_value={
            "success": True,
            "data": [{"id": "1"}],
        })

        result = await _execute_xactions_tool(
            server_config={
                "url": "http://test:3001/mcp",
                "headers": {"X-Consumer-Id": "nowing"},
                "api_key": "key",
            },
            tool_name="x_search_tweets",
            arguments={"query": "ai", "platform": "twitter"},
        )

        assert result["success"] is True
        mock_client.call_tool.assert_awaited_once_with(
            "x_search_tweets",
            {"query": "ai", "platform": "twitter", "dryRun": False},
        )


@pytest.mark.asyncio
async def test_execute_xactions_tool_injects_facebook_auth():
    """_execute_xactions_tool injects accountId for facebook tools only."""
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway import (
        _execute_xactions_tool,
    )

    with (
        patch(
            "app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway.config.XACTIONS_FACEBOOK_ACCOUNT_ID",
            "fb_acc_01",
        ),
        patch(
            "app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway.XActionsMcpClient",
            autospec=True,
        ) as mock_client_cls,
    ):
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.call_tool = AsyncMock(return_value={"success": True, "data": []})

            result = await _execute_xactions_tool(
                server_config={"url": "http://test:3001/mcp"},
                tool_name="x_facebook_group_posts",
                arguments={"url": "https://facebook.com/groups/test"},
            )

            call_args = mock_client.call_tool.call_args[0]
            assert call_args[0] == "x_facebook_group_posts"
            assert call_args[1]["accountId"] == "fb_acc_01"
            assert call_args[1]["authCookie"]["accountId"] == "fb_acc_01"
            assert result["success"] is True


@pytest.mark.asyncio
async def test_facebook_group_requires_target():
    """Facebook group/page scrape returns an error when target/query is missing."""
    res = await _handle_xactions_scrape(
        server_config={"url": "http://test:3001/mcp"},
        platform="facebook",
        action="group_posts",
    )
    assert res.startswith("Error")
    assert "group" in res.lower()


@pytest.mark.asyncio
async def test_facebook_page_requires_target():
    res = await _handle_xactions_scrape(
        server_config={"url": "http://test:3001/mcp"},
        platform="facebook",
        action="page_posts",
    )
    assert res.startswith("Error")
    assert "page" in res.lower()

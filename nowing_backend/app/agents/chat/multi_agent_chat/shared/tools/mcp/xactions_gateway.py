"""XActions Meta-Tool Gateway (Solution 3).

Instead of exposing 150+ granular XActions scraping tools into the LLM system
prompt (which causes severe prompt bloat, high token costs, and tool hallucination),
this module wraps XActions into 3 clean, consolidated meta-tools:
1. `x_search`: Cross-platform keyword/hashtag/user search across Twitter/X, Facebook, Threads, etc.
2. `x_scrape`: Targeted listing/feed scraping (e.g. Marketplace, user posts, trends, hashtags).
3. `x_crawl_post`: Deep post inspection for a specific post URL or ID.

Each meta-tool validates high-level parameters and dispatches dynamically to the
appropriate underlying XActions MCP tool on the daemon.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from app.config import config
from app.proprietary.platforms.xactions.mcp_client import (
    XActionsMcpClient,
    XActionsMcpError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Input Schemas for Meta-Tools
# ---------------------------------------------------------------------------


class XActionsSearchInput(BaseModel):
    """Input for searching posts, tweets, and profiles across social platforms."""

    model_config = ConfigDict(extra="allow")

    query: str = Field(
        ...,
        description="Search keyword, query phrase, or topic to search for.",
    )
    platform: str = Field(
        default="twitter",
        description=(
            "Target platform: 'twitter' (or 'x'), 'facebook', 'threads', 'bluesky', 'mastodon'. "
            "Defaults to 'twitter'."
        ),
    )
    limit: int = Field(
        default=20,
        description="Maximum number of search results to return (1-100). Default is 20.",
    )
    search_type: str | None = Field(
        default=None,
        description=(
            "Category filter for Facebook search: 'posts', 'people', 'pages', 'groups', 'all'. "
            "Only applies when platform is 'facebook'."
        ),
    )


class XActionsScrapeInput(BaseModel):
    """Input for targeted listing and feed scraping on social platforms."""

    model_config = ConfigDict(extra="allow")

    platform: str = Field(
        ...,
        description=(
            "Target platform: 'facebook', 'twitter', 'threads', 'bluesky', 'mastodon', "
            "'tiktok', 'chotot', 'shopee', 'topcv', 'batdongsan', 'masothue', 'b2b_registry'."
        ),
    )
    action: str = Field(
        ...,
        description=(
            "Action/resource to scrape: "
            "'marketplace' (Facebook Marketplace listings), "
            "'hashtag' (Twitter/X posts for a hashtag), "
            "'trends' (trending topics on Twitter/X), "
            "'user_posts' (recent posts/tweets from a specific user), "
            "'group_posts' (posts from a Facebook group), "
            "'page_posts' (posts from a Facebook page), "
            "'search' or 'posts' (generic platform scraper)."
        ),
    )
    query: str | None = Field(
        default=None,
        description="Search keyword (e.g. product name for marketplace, topic category, or query).",
    )
    target: str | None = Field(
        default=None,
        description="Target identifier: username (without @), hashtag (without #), or group/page URL or ID.",
    )
    location: str | None = Field(
        default=None,
        description="Location/city filter (e.g. 'Ho Chi Minh', 'Hanoi'). Supported on Marketplace.",
    )
    min_price: float | None = Field(
        default=None,
        description="Minimum price filter for Marketplace.",
    )
    max_price: float | None = Field(
        default=None,
        description="Maximum price filter for Marketplace.",
    )
    limit: int = Field(
        default=20,
        description="Maximum items to return (1-100). Default is 20.",
    )


class XActionsCrawlPostInput(BaseModel):
    """Input for deep inspection of a specific social post URL or ID."""

    model_config = ConfigDict(extra="allow")

    url: str | None = Field(
        default=None,
        description="Full URL of the post or article to crawl (e.g. Facebook post URL, tweet URL, Threads URL).",
    )
    platform: str | None = Field(
        default=None,
        description=(
            "Platform of the post: 'facebook', 'twitter', 'threads', 'bluesky', 'mastodon'. "
            "If omitted, auto-detected from URL."
        ),
    )
    post_id: str | None = Field(
        default=None,
        description="Platform-specific post ID if URL is not directly available.",
    )
    limit: int = Field(
        default=50,
        description="Maximum number of comments or detail records to return. Default is 50.",
    )


# ---------------------------------------------------------------------------
# Execution and Dispatch Helpers
# ---------------------------------------------------------------------------


def _normalize_platform(raw_platform: str | None) -> str:
    if not raw_platform:
        return "twitter"
    p = raw_platform.strip().lower()
    if p in ("x", "x.com"):
        return "twitter"
    if p in ("fb", "fb.com"):
        return "facebook"
    return p


def _detect_platform_from_url(url: str | None) -> str:
    if not url:
        return "facebook"
    if "://" not in url:
        url = f"https://{url}"
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if "facebook.com" in host or "fb.watch" in host or "fb.com" in host:
        return "facebook"
    if "twitter.com" in host or "x.com" in host:
        return "twitter"
    if "threads.net" in host:
        return "threads"
    if "bsky.app" in host:
        return "bluesky"
    if "tiktok.com" in host:
        return "tiktok"
    return "facebook"


async def _execute_xactions_tool(
    server_config: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Execute a low-level XActions MCP tool via XActionsMcpClient with auth & dryRun defaults."""
    url = server_config.get("url") or getattr(config, "XACTIONS_MCP_URL", "http://localhost:3001/mcp")
    headers = server_config.get("headers") or {}
    api_key = server_config.get("api_key") or getattr(config, "XACTIONS_MCP_API_KEY", "")
    consumer_id = headers.get("X-Consumer-Id") or getattr(config, "XACTIONS_CONSUMER_ID", "nowing")

    # Inject default account id for Facebook tools requiring authentication
    default_account_id = getattr(config, "XACTIONS_FACEBOOK_ACCOUNT_ID", None)
    if default_account_id and "facebook" in tool_name:
        if "authCookie" not in arguments:
            arguments["authCookie"] = {"accountId": default_account_id}
        if "accountId" not in arguments:
            arguments["accountId"] = default_account_id

    # Enforce real scraping data (dryRun: false) unless explicitly requested
    if "dryRun" not in arguments:
        arguments["dryRun"] = False

    async with XActionsMcpClient(url=url, api_key=api_key, consumer_id=consumer_id) as client:
        try:
            return await client.call_tool(tool_name, arguments)
        except XActionsMcpError as exc:
            logger.warning("XActions tool '%s' error: %s (code=%s)", tool_name, exc.message, exc.code)
            return {
                "success": False,
                "error": exc.message,
                "code": exc.code,
                "suggested_action": exc.suggested_action,
            }
        except Exception as exc:
            logger.exception("XActions execution error on '%s': %s", tool_name, exc)
            return {
                "success": False,
                "error": str(exc),
            }


def _format_result(tool_name: str, result: dict[str, Any]) -> str:
    """Format the XActions tool output into a clean string for the agent."""
    if not result.get("success", True):
        error = result.get("error") or result.get("message") or "Execution failed"
        return f"Error executing {tool_name}: {error}"

    data = result.get("data")
    summary = result.get("summary")
    meta = result.get("meta")

    response_payload: dict[str, Any] = {}
    if data is not None:
        response_payload["data"] = data
    if summary:
        response_payload["summary"] = summary
    if meta:
        response_payload["meta"] = meta

    return json.dumps(response_payload, ensure_ascii=False, indent=2, default=str)


# ---------------------------------------------------------------------------
# Meta-Tool Callbacks
# ---------------------------------------------------------------------------


async def _handle_xactions_search(
    server_config: dict[str, Any],
    query: str,
    platform: str = "twitter",
    limit: int = 20,
    search_type: str | None = None,
    **extra: Any,
) -> str:
    normalized = _normalize_platform(platform)

    if normalized == "facebook":
        # Specialized Facebook search (posts, people, pages, groups)
        tool_name = "x_facebook_search"
        arguments = {
            "query": query,
            "type": search_type or "posts",
            "limit": limit,
            "dryRun": False,
        }
    else:
        # Cross-platform social search (Twitter, Bluesky, Mastodon, Threads, Facebook)
        tool_name = "x_search_tweets"
        arguments = {
            "query": query,
            "platform": normalized,
            "limit": limit,
        }

    arguments.update(extra)
    result = await _execute_xactions_tool(server_config, tool_name, arguments)
    return _format_result(tool_name, result)


async def _handle_xactions_scrape(
    server_config: dict[str, Any],
    platform: str,
    action: str,
    query: str | None = None,
    target: str | None = None,
    location: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 20,
    **extra: Any,
) -> str:
    normalized_platform = _normalize_platform(platform)
    act = action.strip().lower()

    if normalized_platform == "facebook" and act == "marketplace":
        tool_name = "x_facebook_marketplace"
        arguments: dict[str, Any] = {
            "query": query or target or "all",
            "limit": limit,
            "dryRun": False,
        }
        if location:
            arguments["location"] = location
        if min_price is not None:
            arguments["minPrice"] = min_price
        if max_price is not None:
            arguments["maxPrice"] = max_price

    elif normalized_platform == "facebook" and act in ("group_posts", "group"):
        tool_name = "x_facebook_group_posts"
        url = target or query
        if not url:
            return "Error: Facebook group scrape requires a target or query (group id or URL)."
        if not url.startswith("http"):
            url = f"https://www.facebook.com/groups/{url}"
        arguments = {"url": url, "limit": limit, "dryRun": False}

    elif normalized_platform == "facebook" and act in ("page_posts", "page"):
        tool_name = "x_facebook_posts"
        url = target or query
        if not url:
            return "Error: Facebook page scrape requires a target or query (page id or URL)."
        if not url.startswith("http"):
            url = f"https://www.facebook.com/{url}"
        arguments = {"url": url, "limit": limit, "dryRun": False}

    elif normalized_platform == "twitter" and act == "hashtag":
        tool_name = "x_get_hashtag"
        tag = (target or query or "").lstrip("#")
        arguments = {"hashtag": tag, "limit": limit}

    elif normalized_platform == "twitter" and act == "trends":
        tool_name = "x_get_trends"
        arguments = {"limit": limit}
        if query:
            arguments["category"] = query

    elif act in ("user_posts", "tweets", "user_tweets"):
        tool_name = "x_get_tweets"
        username = (target or query or "").lstrip("@")
        arguments = {
            "username": username,
            "platform": normalized_platform,
            "limit": limit,
        }

    elif normalized_platform in ("tiktok", "chotot", "shopee", "topcv", "batdongsan", "masothue", "b2b_registry", "linkedin_company"):
        tool_name = "x_scrape"
        arguments = {
            "platform": normalized_platform,
            "action": act,
            "query": query,
            "target": target,
            "limit": limit,
        }

    else:
        # Fallback to x_crawl_post or x_search_tweets
        if target and target.startswith("http"):
            tool_name = "x_crawl_post"
            arguments = {"platform": normalized_platform, "url": target, "limit": limit}
        else:
            tool_name = "x_search_tweets"
            arguments = {
                "query": query or target or "",
                "platform": normalized_platform,
                "limit": limit,
            }

    arguments.update(extra)
    result = await _execute_xactions_tool(server_config, tool_name, arguments)
    return _format_result(tool_name, result)


async def _handle_xactions_crawl_post(
    server_config: dict[str, Any],
    url: str | None = None,
    platform: str | None = None,
    post_id: str | None = None,
    limit: int = 50,
    **extra: Any,
) -> str:
    if not url and not post_id:
        return "Error: x_crawl_post requires a url or post_id."
    target_platform = _normalize_platform(platform or _detect_platform_from_url(url))
    tool_name = "x_crawl_post"
    arguments: dict[str, Any] = {
        "platform": target_platform,
        "limit": limit,
    }
    if url:
        arguments["url"] = url
    if post_id:
        arguments["postId"] = post_id

    arguments.update(extra)
    result = await _execute_xactions_tool(server_config, tool_name, arguments)
    return _format_result(tool_name, result)


# ---------------------------------------------------------------------------
# Factory: Create the 3 Meta-Tools for LangChain
# ---------------------------------------------------------------------------


def create_xactions_meta_tools(
    connector_id: int,
    connector_name: str,
    server_config: dict[str, Any],
    *,
    trusted_tools: list[str] | None = None,
    bypass_internal_hitl: bool = True,
) -> list[StructuredTool]:
    """Create the 3 consolidated XActions meta-tools for a workspace connector.

    All 3 meta-tools are read-only and bypass Human-In-The-Loop approval.
    """
    url = server_config.get("url") or getattr(config, "XACTIONS_MCP_URL", "http://localhost:3001/mcp")

    async def search_wrapper(**kwargs: Any) -> str:
        return await _handle_xactions_search(server_config, **kwargs)

    async def scrape_wrapper(**kwargs: Any) -> str:
        return await _handle_xactions_scrape(server_config, **kwargs)

    async def crawl_post_wrapper(**kwargs: Any) -> str:
        return await _handle_xactions_crawl_post(server_config, **kwargs)

    search_tool = StructuredTool(
        name="x_search",
        description=(
            "[XActions Social] Search posts, tweets, and profiles across social media "
            "(Twitter/X, Facebook, Threads, Bluesky, Mastodon). Use this to find discussions, "
            "opinions, and market trends."
        ),
        coroutine=search_wrapper,
        args_schema=XActionsSearchInput,
        metadata={
            "mcp_transport": "http",
            "mcp_url": url,
            "mcp_connector_name": connector_name,
            "mcp_connector_id": connector_id,
            "mcp_is_generic": False,
            "hitl": False,
            "mcp_original_tool_name": "x_search",
        },
    )

    scrape_tool = StructuredTool(
        name="x_scrape",
        description=(
            "[XActions Social] Scrape structured listings and feeds from social platforms. "
            "Supports Facebook Marketplace (product listings, prices, locations), Twitter hashtags "
            "and trends, user feeds, and group/page posts."
        ),
        coroutine=scrape_wrapper,
        args_schema=XActionsScrapeInput,
        metadata={
            "mcp_transport": "http",
            "mcp_url": url,
            "mcp_connector_name": connector_name,
            "mcp_connector_id": connector_id,
            "mcp_is_generic": False,
            "hitl": False,
            "mcp_original_tool_name": "x_scrape",
        },
    )

    crawl_post_tool = StructuredTool(
        name="x_crawl_post",
        description=(
            "[XActions Social] Crawl full content, comment tree, and media details for a specific "
            "post URL or ID across Facebook, Twitter/X, Threads, and Bluesky."
        ),
        coroutine=crawl_post_wrapper,
        args_schema=XActionsCrawlPostInput,
        metadata={
            "mcp_transport": "http",
            "mcp_url": url,
            "mcp_connector_name": connector_name,
            "mcp_connector_id": connector_id,
            "mcp_is_generic": False,
            "hitl": False,
            "mcp_original_tool_name": "x_crawl_post",
        },
    )

    return [search_tool, scrape_tool, crawl_post_tool]

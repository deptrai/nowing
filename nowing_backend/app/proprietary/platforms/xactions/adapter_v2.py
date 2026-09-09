"""XActions Social Adapter v2 — MCP streamable-http (Story 21.8a / 21.8d).

This is the intended replacement for the stdio-based `adapter.py`. It uses
`XActionsMcpClient` to call XActions over HTTP and maintains a mapping from
Nowing `SocialMonitoredTarget` records to XActions tool/argument pairs.

It intentionally does **not** spawn `node src/mcp/server.js`; it relies on
XActions running with `MCP_TRANSPORT=http PORT=3001`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.config import config
from app.proprietary.platforms.xactions.constants import STREAM_SOCIAL_RAW_POSTS
from app.proprietary.platforms.xactions.mcp_client import (
    XActionsMcpClient,
    XActionsMcpError,
)
from app.proprietary.platforms.xactions.models import SocialPostData

logger = logging.getLogger(__name__)


# Map Nowing platform targets to XActions tool/action pairs.
# VN-domain platforms are dispatched via the generic `x_scrape` tool once
# XActions exposes it (Story 21.8a requirement). Until then, `x_crawl_post`
# is used as a fallback for post detail.
PLATFORM_TOOL_MAP: dict[str, dict[str, Any]] = {
    "facebook_group": {
        "tool": "x_facebook_group_posts",
        "args_builder": lambda t: {"url": _facebook_group_url(t.target_id), "limit": 20},
    },
    "facebook_page": {
        "tool": "x_facebook_posts",
        "args_builder": lambda t: {"url": _facebook_page_url(t.target_id), "limit": 20},
    },
    "twitter_keyword": {
        "tool": "x_search_tweets",
        "args_builder": lambda t: {"query": t.target_id, "limit": 20},
    },
    "twitter_user": {
        "tool": "x_get_tweets",
        "args_builder": lambda t: {"username": t.target_id.strip("@"), "limit": 20},
    },
    "tiktok_hashtag": {
        "tool": "x_scrape",
        "args_builder": lambda t: {"platform": "tiktok", "action": "posts", "hashtag": t.target_id},
    },
    "chotot_category": {
        "tool": "x_scrape",
        "args_builder": lambda t: {"platform": "chotot", "action": "posts", "category": t.target_id},
    },
    "shopee_keyword": {
        "tool": "x_scrape",
        "args_builder": lambda t: {"platform": "shopee", "action": "search", "keyword": t.target_id},
    },
    "topcv_search": {
        "tool": "x_scrape",
        "args_builder": lambda t: {"platform": "topcv", "action": "search", "query": t.target_id},
    },
    "vietnamworks_search": {
        "tool": "x_scrape",
        "args_builder": lambda t: {"platform": "vietnamworks", "action": "search", "query": t.target_id},
    },
    "linkedin_company": {
        "tool": "x_scrape",
        "args_builder": lambda t: {"platform": "linkedin", "action": "company", "company": t.target_id},
    },
    "batdongsan_category": {
        "tool": "x_scrape",
        "args_builder": lambda t: {"platform": "batdongsan", "action": "posts", "category": t.target_id},
    },
    "masothue_lookup": {
        "tool": "x_scrape",
        "args_builder": lambda t: {"platform": "masothue", "action": "lookup", "taxCode": t.target_id},
    },
    "b2b_registry_search": {
        "tool": "x_scrape",
        "args_builder": lambda t: {"platform": "b2b_registry", "action": "search", "query": t.target_id},
    },
}


def _facebook_group_url(target_id: str) -> str:
    if target_id.startswith("http"):
        return target_id
    return f"https://www.facebook.com/groups/{target_id}"


def _facebook_page_url(target_id: str) -> str:
    if target_id.startswith("http"):
        return target_id
    return f"https://www.facebook.com/{target_id}"


def _normalize_platform_for_post(platform: str) -> str:
    """Map target platform to social post platform."""
    # b2b_registry_search → "b2b_registry" (preserve multi-part family names)
    if platform == "b2b_registry_search":
        return "b2b_registry"
    return platform.split("_")[0]


class UniversalScrapeTargetMapper:
    """Map a Nowing social target to an XActions tool call.

    VN-domain platforms are dispatched via `x_scrape` when available. If the
    XActions daemon does not yet expose `x_scrape` (per INTEGRATION-PLAN),
    callers should treat an MCP `tool_not_found`/`XACT_404`-style failure as
    a signal to fall back to `x_crawl_post` for post-detail-only ingestion.
    """

    @staticmethod
    def map(target: Any) -> tuple[str, dict[str, Any]]:
        platform = getattr(target, "platform", None)
        mapping = PLATFORM_TOOL_MAP.get(platform)
        if not mapping:
            raise ValueError(f"Unsupported social platform: {platform}")
        return mapping["tool"], mapping["args_builder"](target)

    @staticmethod
    def fallback_crawl_post(target: Any) -> tuple[str, dict[str, Any]]:
        """Return an `x_crawl_post` fallback call for post-detail scraping.

        Used when `x_scrape` is not yet exposed by XActions (AC 7).
        """
        target_url = getattr(target, "target_url", None) or getattr(target, "target_id", "")
        if not target_url:
            raise ValueError("x_crawl_post fallback requires a target_url or target_id")
        return "x_crawl_post", {"url": target_url}


class XActionsSocialAdapterV2:
    """Thin adapter over `XActionsMcpClient` for social ingestion."""

    def __init__(
        self,
        client: XActionsMcpClient | None = None,
        default_account_id: str ^ None = None,
    ):
        self.client = client
        self._owns_client = client is None
        self.default_account_id = (
            default_account_id or getattr(config, "XACTIONS_FACEBOOK_ACCOUNT_ID", None)
        )

    async def _get_client(self) -> XActionsMcpClient:
        if self.client is None:
            self.client = XActionsMcpClient()
            await self.client.__aenter__()
        return self.client

    async def fetch_posts_for_target(self, target: Any) -> list[dict[str, Any]]:
        """Fetch posts for a monitored target via XActions MCP."""
        client = await self._get_client()
        tool_name, arguments = UniversalScrapeTargetMapper.map(target)

        account_id = getattr(target, "account_id", None) or self.default_account_id
        if account_id:
            arguments["accountId"] = account_id
        if getattr(target, "proxy_url", None):
            arguments["proxyUrl"] = target.proxy_url

        try:
            result = await client.call_tool(tool_name, arguments)
        except XActionsMcpError as exc:
            logger.warning(
                "XActions tool %s failed: %s (code=%s, retry_after=%s)",
                tool_name,
                exc.message,
                exc.code,
                exc.retry_after,
            )
            raise

        if not result.get("success"):
            raise RuntimeError(
                f"XActions tool {tool_name} returned success=False: {result.get('error')}"
            )

        data = result.get("data", [])
        posts: list[SocialPostData] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            published_at = item.get("publishedAt") or item.get("published_at")
            if isinstance(published_at, str):
                try:
                    published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                except ValueError:
                    published_at = None
            posts.append(
                SocialPostData(
                    platform=_normalize_platform_for_post(target.platform),
                    external_post_id=item.get("id") or item.get("externalId") or "",
                    author_id=item.get("authorId") or item.get("author_id"),
                    author_name=item.get("authorName") or item.get("author_name"),
                    author_url=item.get("authorUrl") or item.get("author_url"),
                    post_url=item.get("postUrl") or item.get("post_url"),
                    content=item.get("content") or item.get("text") or "",
                    reactions_count=item.get("reactions") or item.get("reactionsCount") or 0,
                    comments_count=item.get("comments") or item.get("commentsCount") or 0,
                    shares_count=item.get("shares") or item.get("sharesCount") or 0,
                    media_urls=item.get("mediaUrls") or item.get("media_urls") or [],
                    raw_entities=item.get("entities") or item.get("raw_entities") or {},
                    published_at=published_at,
                    category=item.get("category") or item.get("post_category"),
                    storage_ref=item.get("storageRef") or item.get("storage_ref"),
                    scraper_id=item.get("scraperId") or item.get("scraper_id"),
                    benchmark_health=item.get("benchmarkHealth") or item.get("benchmark_health"),
                    benchmark_alert=item.get("benchmarkAlert") or item.get("benchmark_alert"),
                    target_id=getattr(target, "id", None),
                    workspace_id=getattr(target, "workspace_id", None),
                )
            )
        return posts

    async def ingest_raw_post_to_stream(
        self,
        post: SocialPostData,
        redis_client: Any,
    ) -> str | None:
        """Push a thin social post event to Redis Stream (AD-SOC-4)."""
        payload = post.to_dict()
        try:
            msg_id = await redis_client.xadd(
                STREAM_SOCIAL_RAW_POSTS,
                payload,
                maxlen=20000,
                approximate=True,
            )
            return msg_id
        except Exception as exc:
            logger.exception("Redis xadd failed on %s: %s", STREAM_SOCIAL_RAW_POSTS, exc)
            return None

    async def close(self) -> None:
        if self.client is not None and self._owns_client:
            await self.client.__aexit__(None, None, None)
            self.client = None

    async def __aenter__(self) -> XActionsSocialAdapterV2:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

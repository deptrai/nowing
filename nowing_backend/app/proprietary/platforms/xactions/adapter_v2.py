"""XActions Social Adapter v2 — MCP streamable-http (Story 21.8a / 21.8d).

This is the intended replacement for the stdio-based `adapter.py`. It uses
`XActionsMcpClient` to call XActions over HTTP and maintains a mapping from
Nowing `SocialMonitoredTarget` records to XActions tool/argument pairs.

It intentionally does **not** spawn `node src/mcp/server.js`; it relies on
XActions running with `MCP_TRANSPORT=http PORT=3001`.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.config import config
from app.proprietary.platforms.xactions.action_matrix import (
    CanonicalActionMatrix,
    derive_platform_action,
)
from app.proprietary.platforms.xactions.constants import STREAM_SOCIAL_RAW_POSTS
from app.proprietary.platforms.xactions.mcp_client import (
    XActionsMcpClient,
    XActionsMcpError,
    get_shared_client,
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


class TargetUnsupportedError(RuntimeError):
    """Raised when a target cannot be scraped because platform/URL is unsupported or fallback fails permanently."""


def _is_tool_not_found_error(exc: XActionsMcpError) -> bool:
    code_str = str(exc.code) if exc.code is not None else ""
    if code_str in ("XACT_404", "tool_not_found", "404"):
        return True
    if isinstance(exc.message, str):
        msg_lower = exc.message.lower()
        if "tool_not_found" in msg_lower or "tool not found" in msg_lower:
            return True
    return False


def _is_permanent_fallback_error(exc: XActionsMcpError) -> bool:
    code_str = str(exc.code) if exc.code is not None else ""
    if code_str in ("XACT_404", "XACT_4001", "tool_not_found", "404", "4001"):
        return True
    if isinstance(exc.message, str):
        msg_lower = exc.message.lower()
        if any(term in msg_lower for term in ("tool_not_found", "tool not found", "action not available", "unsupported")):
            return True
    return False


class UniversalScrapeTargetMapper:
    """Map a Nowing social target to an XActions tool call.

    VN-domain platforms are dispatched via `x_scrape` when available. If the
    XActions daemon does not yet expose `x_scrape` (per INTEGRATION-PLAN),
    callers should treat an MCP `tool_not_found`/`XACT_404`-style failure as
    a signal to fall back to `x_crawl_post` for post-detail-only ingestion.

    When ``XACTIONS_USE_UNIFIED_DISPATCH`` is ON, platforms that were already
    dispatched via ``x_scrape`` in ``PLATFORM_TOOL_MAP`` resolve their
    ``(platform, action)`` pair from the :class:`CanonicalActionMatrix` and
    emit the nested ``{platform, action, args, context}`` envelope per AD-2.
    Facebook/Twitter entries that still use dedicated legacy tools
    (``x_facebook_group_posts``, ``x_search_tweets``, …) are left untouched —
    unified dispatch only replaces the ``x_scrape`` rows.
    """

    @staticmethod
    def _unified_envelope(
        target: Any,
        platform_kind: str,
        matrix: dict[str, dict[str, dict[str, Any]]],
    ) -> tuple[str, dict[str, Any]]:
        """Build the nested ``x_scrape`` envelope for a matrix-backed platform.

        Returns ``("x_scrape", {platform, action, args: {...}, context:
        {targetId, workspaceId}})``. Action args are populated from the
        descriptor's ``requiredArgs`` — the target's ``target_id`` is bound to
        the single required arg (all current matrix entries have exactly one).
        """
        platform, action = derive_platform_action(platform_kind, matrix)
        descriptor = matrix[platform][action]
        required_args = list(descriptor.get("requiredArgs") or [])

        target_id_value = getattr(target, "target_id", None)
        args: dict[str, Any] = {}
        if required_args:
            if len(required_args) == 1:
                if not target_id_value:
                    raise ValueError(
                        f"target_id required for action {action}"
                    )
                args[required_args[0]] = target_id_value
            else:
                # Multi-required-arg descriptors are not yet produced by the
                # static matrix; surface them loudly rather than guess binding.
                raise ValueError(
                    f"Action {action} requires multiple args {required_args}; "
                    "automatic binding not supported"
                )

        context = {
            "targetId": getattr(target, "id", None) or getattr(target, "target_id", None),
            "workspaceId": getattr(target, "workspace_id", None),
        }

        arguments: dict[str, Any] = {
            "platform": platform,
            "action": action,
            "args": args,
            "context": context,
        }
        return "x_scrape", arguments

    @staticmethod
    def map(target: Any) -> tuple[str, dict[str, Any]]:
        """Map a target to ``(tool_name, arguments)``.

        Sync — never touches the network. Under flag ON this consults
        :meth:`CanonicalActionMatrix.get_sync` (fresh cache or static
        fallback); under flag OFF it uses ``PLATFORM_TOOL_MAP`` verbatim.
        """
        platform = getattr(target, "platform", None)

        if getattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", False):
            mapping = PLATFORM_TOOL_MAP.get(platform)
            if mapping is None:
                raise ValueError(f"Unsupported social platform: {platform}")
            # Legacy dedicated tools (facebook/twitter) stay as-is even when
            # the flag is ON — unified dispatch only replaces x_scrape rows.
            if mapping["tool"] != "x_scrape":
                return mapping["tool"], mapping["args_builder"](target)
            matrix = CanonicalActionMatrix.get_sync()
            return UniversalScrapeTargetMapper._unified_envelope(
                target, platform, matrix
            )

        mapping = PLATFORM_TOOL_MAP.get(platform)
        if not mapping:
            raise ValueError(f"Unsupported social platform: {platform}")
        return mapping["tool"], mapping["args_builder"](target)

    @staticmethod
    async def map_async(
        target: Any,
        client: Any | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Async variant — refreshes the action matrix when the flag is ON.

        Flag OFF → delegates to :meth:`map` unchanged. Flag ON → awaits
        ``CanonicalActionMatrix.get(client)`` so the TTL cache can refresh
        from ``x_actions_list`` before resolving ``(platform, action)``.
        """
        if not getattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", False):
            return UniversalScrapeTargetMapper.map(target)

        platform = getattr(target, "platform", None)
        mapping = PLATFORM_TOOL_MAP.get(platform)
        if mapping is None:
            raise ValueError(f"Unsupported social platform: {platform}")
        if mapping["tool"] != "x_scrape":
            return mapping["tool"], mapping["args_builder"](target)

        matrix = await CanonicalActionMatrix.get(client)
        return UniversalScrapeTargetMapper._unified_envelope(
            target, platform, matrix
        )

    @staticmethod
    def fallback_crawl_post(target: Any) -> tuple[str, dict[str, Any]]:
        """Return an `x_crawl_post` fallback call for post-detail scraping.

        Used when `x_scrape` is not yet exposed by XActions (AC 7).
        """
        platform = _normalize_platform_for_post(getattr(target, "platform", "") or "")
        if not platform:
            raise TargetUnsupportedError(
                f"Target {getattr(target, 'id', None)} lacks valid platform for x_crawl_post fallback"
            )
        raw_url = str(getattr(target, "target_url", None) or "").strip() or str(
            getattr(target, "target_id", "") or ""
        ).strip()
        target_url = raw_url
        if not target_url.lower().startswith(("http://", "https://")):
            raise TargetUnsupportedError(
                f"Target {getattr(target, 'id', None)} lacks valid HTTP(S) URL for x_crawl_post fallback: {target_url!r}"
            )
        return "x_crawl_post", {"platform": platform, "url": target_url}


class XActionsSocialAdapterV2:
    """Thin adapter over `XActionsMcpClient` for social ingestion."""

    def __init__(
        self,
        client: XActionsMcpClient | None = None,
        default_account_id: str | None = None,
    ):
        self.client = client
        self._is_shared = client is None
        self._owns_client = not self._is_shared
        self.default_account_id = (
            default_account_id or getattr(config, "XACTIONS_FACEBOOK_ACCOUNT_ID", None)
        )

    async def _get_client(self) -> XActionsMcpClient:
        if not self._is_shared and self.client is not None:
            return self.client
        return await get_shared_client()

    async def fetch_posts_for_target(self, target: Any) -> list[SocialPostData]:
        """Fetch posts for a monitored target via XActions MCP."""
        client = await self._get_client()
        if getattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", False):
            tool_name, arguments = await UniversalScrapeTargetMapper.map_async(
                target, client
            )
        else:
            tool_name, arguments = UniversalScrapeTargetMapper.map(target)

        account_id = getattr(target, "account_id", None) or self.default_account_id
        if account_id:
            arguments["accountId"] = account_id
        if getattr(target, "proxy_url", None):
            arguments["proxyUrl"] = target.proxy_url

        # XActions scraping tools default to dryRun=true; force execution when
        # the caller actually wants data (unless explicitly set).
        if "dryRun" not in arguments:
            arguments["dryRun"] = False

        effective_tool = tool_name
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
            if _is_tool_not_found_error(exc):
                logger.warning(
                    "XActions primary tool %s not found (code=%s) for target %s (platform=%s). Attempting x_crawl_post fallback.",
                    tool_name,
                    exc.code,
                    getattr(target, "id", None),
                    getattr(target, "platform", None),
                )
                fallback_tool, fallback_args = UniversalScrapeTargetMapper.fallback_crawl_post(target)
                if account_id:
                    fallback_args["accountId"] = account_id
                if getattr(target, "proxy_url", None):
                    fallback_args["proxyUrl"] = target.proxy_url
                if "dryRun" not in fallback_args:
                    fallback_args["dryRun"] = False

                effective_tool = fallback_tool
                try:
                    result = await client.call_tool(fallback_tool, fallback_args)
                except XActionsMcpError as fallback_exc:
                    logger.warning(
                        "XActions fallback tool %s failed for target %s (platform=%s): %s (code=%s, retry_after=%s)",
                        fallback_tool,
                        getattr(target, "id", None),
                        getattr(target, "platform", None),
                        fallback_exc.message,
                        fallback_exc.code,
                        fallback_exc.retry_after,
                    )
                    if _is_permanent_fallback_error(fallback_exc):
                        raise TargetUnsupportedError(
                            f"Fallback {fallback_tool} failed permanently with code {fallback_exc.code} for target {getattr(target, 'id', None)}: {fallback_exc.message}"
                        ) from fallback_exc
                    raise
            else:
                raise

        if not result.get("success"):
            err_msg = result.get("error") or "unknown error"
            if effective_tool == "x_crawl_post":
                # Only a clean permanent failure should retire the target. A
                # success=False envelope carries no MCP code, so classify by the
                # error text; ambiguous/transient messages fall through to a
                # RuntimeError so the existing retry/pause lifecycle handles them.
                err_lower = str(err_msg).lower()
                if any(
                    term in err_lower
                    for term in (
                        "not found",
                        "tool_not_found",
                        "404",
                        "4001",
                        "unsupported",
                        "action not available",
                        "invalid url",
                        "blocked",
                    )
                ):
                    raise TargetUnsupportedError(
                        f"Fallback {effective_tool} returned success=False for target {getattr(target, 'id', None)}: {err_msg}"
                    )
            raise RuntimeError(
                f"XActions tool {effective_tool} returned success=False: {err_msg}"
            )

        data = result.get("data", [])
        if isinstance(data, dict):
            data = [data]
        elif isinstance(data, list) or (hasattr(data, "__iter__") and not isinstance(data, (str, bytes))):
            pass
        else:
            data = []

        posts: list[SocialPostData] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            published_at = item.get("publishedAt") or item.get("published_at")
            if isinstance(published_at, str):
                try:
                    published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    published_at = None
            elif isinstance(published_at, (int, float)):
                try:
                    # XActions/scrapers may emit millisecond epoch timestamps;
                    # normalize anything beyond a plausible seconds range.
                    ts = published_at / 1000 if published_at > 1e11 else published_at
                    published_at = datetime.fromtimestamp(ts, tz=UTC)
                except (ValueError, OSError, OverflowError):
                    published_at = None

            post_id = next(
                (
                    item[k]
                    for k in ("id", "externalId", "postId", "post_id")
                    if item.get(k) is not None
                ),
                None,
            )
            post_url = item.get("postUrl") or item.get("post_url") or item.get("url")
            if post_id is None or post_id == "":
                if post_url:
                    post_id = post_url
                else:
                    logger.warning("Skipping post without identifiable external ID: %s", item)
                    continue

            raw_entities = item.get("entities") or item.get("raw_entities") or {}
            if not isinstance(raw_entities, dict):
                # Scrapers may emit entities as a list of dicts; coerce to a
                # dict keyed by "items" so consumers calling .get(...) don't crash.
                raw_entities = {"items": raw_entities}

            posts.append(
                SocialPostData(
                    platform=_normalize_platform_for_post(getattr(target, "platform", "") or ""),
                    external_post_id=str(post_id)[:255],
                    author_id=item.get("authorId") or item.get("author_id"),
                    author_name=item.get("authorName") or item.get("author_name"),
                    author_url=item.get("authorUrl") or item.get("author_url"),
                    post_url=item.get("postUrl") or item.get("post_url") or item.get("url"),
                    content=item.get("content") or item.get("text") or "",
                    reactions_count=item.get("reactions") or item.get("reactionsCount") or 0,
                    comments_count=item.get("comments") or item.get("commentsCount") or 0,
                    shares_count=item.get("shares") or item.get("sharesCount") or 0,
                    media_urls=item.get("mediaUrls") or item.get("media_urls") or [],
                    raw_entities=raw_entities,
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
        """Push a thin social post event to Redis Stream (AD-SOC-4).

        .. deprecated:: Story 36.4 / AD-4
            Legacy dual-write bridge. In the target architecture (AD-4 Sole Writer),
            XActions publishes raw post events directly to stream:social:raw_posts
            via its AbstractCrawler stream hook (REQ-X2).
            Nowing acts solely as a consumer of this stream. This method is bypassed
            when XACTIONS_STREAM_SINGLE_WRITER_ENABLED is True and will be removed
            permanently once XActions REQ-X2 is confirmed live in production.
        """
        if getattr(config, "XACTIONS_STREAM_SINGLE_WRITER_ENABLED", False):
            logger.debug(
                "Skipping ingest_raw_post_to_stream: XACTIONS_STREAM_SINGLE_WRITER_ENABLED is active"
            )
            return None

        # Build payload matching the consumer schema in social_stream_worker.
        # ``post.to_dict()`` is unsafe here: asdict() keeps ``None`` fields which
        # Redis ``xadd`` rejects with ``DataError``. Mirror the legacy v1 adapter
        # (``adapter.py:ingest_raw_post_to_stream``) and serialize datetimes /
        # collections to strings, omitting ``None`` optionals entirely.
        payload: dict[str, Any] = {
            "platform": post.platform,
            "external_post_id": post.external_post_id,
            "author_id": post.author_id or "",
            "author_name": post.author_name or "",
            "author_url": post.author_url or "",
            "post_url": post.post_url or "",
            "content": post.content or "",
            "reactions_count": str(post.reactions_count),
            "comments_count": str(post.comments_count),
            "shares_count": str(post.shares_count),
            "published_at": post.published_at.isoformat() if post.published_at else "",
            "media_urls": json.dumps(post.media_urls or []),
            "schema_version": "1",
        }
        if post.target_id is not None:
            payload["target_id"] = str(post.target_id)
        if post.workspace_id is not None:
            payload["workspace_id"] = str(post.workspace_id)
        if post.client_id is not None:
            payload["client_id"] = post.client_id
        if post.category is not None:
            payload["category"] = post.category
        if post.storage_ref is not None:
            payload["storage_ref"] = post.storage_ref
        if post.scraper_id is not None:
            payload["scraper_id"] = post.scraper_id
        if post.benchmark_health is not None:
            payload["benchmark_health"] = post.benchmark_health
        if post.benchmark_alert is not None:
            payload["benchmark_alert"] = "true" if post.benchmark_alert else "false"
        if post.raw_entities:
            payload["raw_entities"] = json.dumps(post.raw_entities)
        try:
            msg_id = await redis_client.xadd(
                STREAM_SOCIAL_RAW_POSTS,
                payload,
                maxlen=20000,
                approximate=True,
            )
            return msg_id
        except Exception as exc:  # best-effort Redis stream publish; doesn't fail caller
            logger.exception("Redis xadd failed on %s: %s", STREAM_SOCIAL_RAW_POSTS, exc)
            return None

    async def close(self) -> None:
        if not self._is_shared and self.client is not None:
            await self.client.__aexit__(None, None, None)
            self.client = None

    async def __aenter__(self) -> XActionsSocialAdapterV2:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

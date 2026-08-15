"""XActions Social Adapter (Facebook Groups & Twitter Feed Ingress).

Governed by Architecture Spine (AD-SOC-1 to AD-SOC-7):
- AD-SOC-1: Zero-Reinvention XActions Engine Integration
- AD-SOC-2: Stealth Anti-Detection & Fingerprint Delegation
- AD-SOC-3: Sticky SOCKS5 Residential Proxy Binding (1-to-1 per account)
- AD-SOC-4: Decoupled Redis Stream Event Buffer (`stream:social:raw_posts`)
- AD-SOC-6: Idempotent Social Post Storage
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import redis.asyncio as aioredis
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.config import config

logger = logging.getLogger(__name__)

STREAM_SOCIAL_RAW_POSTS = "stream:social:raw_posts"
XACTIONS_PROXY_REDIS_KEY = "xactions:account_proxies"
_XACTIONS_MCP_SERVER = "src/mcp/server.js"
_PROXY_REDIS_FAILURE_BACKOFF_SECONDS = 60.0


class XActionsMcpError(RuntimeError):
    """Raised when the XActions MCP server returns an error."""


@dataclass
class SocialPostData:
    platform: str  # 'facebook', 'twitter'
    external_post_id: str
    author_id: str | None = None
    author_name: str | None = None
    author_url: str | None = None
    post_url: str | None = None
    content: str | None = None
    intent_tag: str | None = None
    fit_score: float = 0.0
    reactions_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    media_urls: list[str] = field(default_factory=list)
    raw_entities: dict[str, Any] = field(default_factory=dict)
    published_at: datetime | None = None
    target_id: int | None = None
    workspace_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.published_at:
            data["published_at"] = self.published_at.isoformat()
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class SocialMonitoredTargetData:
    platform: str  # 'facebook_group', 'facebook_page', 'twitter_keyword', 'twitter_user'
    target_id: str
    target_name: str
    target_url: str | None = None
    category: str = "general"
    is_active: bool = True
    realtime_stream: bool = False
    scrape_interval_minutes: int = 15
    status: str = "active"


def _to_int(raw_value: Any) -> int:
    """Convert a raw engagement count to an integer, defaulting to 0 on failure.

    Handles human-readable suffixes (K, M, B, T) and numeric/empty values.
    """
    if raw_value is None or raw_value == "":
        return 0
    if isinstance(raw_value, bool):
        return int(raw_value)
    if isinstance(raw_value, (int, float)):
        if not math.isfinite(raw_value):
            return 0
        return int(raw_value)
    if not isinstance(raw_value, str):
        return 0

    s = raw_value.strip().replace(",", "")
    if not s:
        return 0

    m = re.fullmatch(r"([\d.]+)\s*([KkMmBbTt])?", s)
    if m:
        try:
            num = float(m.group(1))
        except ValueError:
            return 0
        if not math.isfinite(num):
            return 0
        suffix = m.group(2)
        multiplier = 1.0
        if suffix:
            multipliers = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
            multiplier = multipliers.get(suffix.upper(), 1.0)
        result = num * multiplier
        if not math.isfinite(result):
            return 0
        return int(result)

    try:
        num = float(s)
        if not math.isfinite(num):
            return 0
        return int(num)
    except ValueError:
        return 0


def _parse_published_at(value: Any) -> datetime | None:
    """Parse a published timestamp, returning None and logging on failure."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None

    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(v)
    except ValueError:
        pass

    for fmt in (
        "%a %b %d %H:%M:%S %z %Y",
        "%a %b %d %H:%M:%S %Y",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue

    logger.warning(
        "Could not parse published timestamp %r; leaving published_at=None",
        value,
    )
    return None


class XActionsSocialAdapter:
    """Orchestrator client interacting with the XActions MCP server."""

    def __init__(
        self,
        xactions_path: str | None = None,
        proxy_url: str | None = None,
        timeout: float | None = None,
        redis_client: aioredis.Redis | None = None,
    ):
        # Resolve XActions installation path: explicit > env/config.
        resolved = xactions_path or getattr(config, "XACTIONS_PATH", "")
        self.xactions_path = resolved
        self.default_proxy_url = proxy_url
        self.default_timeout = max(1.0, timeout or getattr(
            config, "XACTIONS_TIMEOUT_SECONDS", 30
        ))

        # AD-SOC-3: in-memory cache + durable Redis backing for proxy bindings.
        self._account_proxies: dict[str, str] = {}
        self._proxy_redis_client = redis_client
        self._proxy_redis_available: bool | None = None
        self._proxy_redis_last_failure = 0.0

    def _resolve_mcp_server_params(self) -> StdioServerParameters:
        """Return stdio parameters for the XActions MCP server.

        ponytail: Spawns a fresh MCP server per call. Reuse would require
        per-account proxy/browser isolation that the current XActions server
        does not expose through its stdio transport.
        """
        if self.xactions_path:
            server_js = os.path.join(self.xactions_path, _XACTIONS_MCP_SERVER)
            if not os.path.isfile(server_js):
                raise RuntimeError(
                    f"XActions MCP server not found at {server_js}. "
                    "Set XACTIONS_PATH to a valid XActions checkout or install `npx xactions-mcp`."
                )
            return StdioServerParameters(
                command="node",
                args=["src/mcp/server.js"],
                cwd=self.xactions_path,
                env={"XACTIONS_MODE": os.getenv("XACTIONS_MODE") or "local"},
            )

        npx = shutil.which("npx")
        if npx:
            return StdioServerParameters(
                command=npx,
                args=["xactions-mcp"],
                env={"XACTIONS_MODE": os.getenv("XACTIONS_MODE") or "local"},
            )

        raise RuntimeError(
            "XActions not configured: set XACTIONS_PATH to a local checkout, "
            "or ensure `npx xactions-mcp` is available."
        )

    def _proxy_redis_connect_timeout(self) -> float:
        """Short timeout for local Redis probes; longer for remote hosts."""
        try:
            host = urlparse(config.REDIS_APP_URL).hostname or "localhost"
        except ValueError:
            host = "localhost"
        return 0.2 if host in ("localhost", "127.0.0.1", "::1") else 2.0

    async def _get_proxy_redis_client(self) -> aioredis.Redis | None:
        if self._proxy_redis_client is not None and self._proxy_redis_available:
            return self._proxy_redis_client

        if (
            self._proxy_redis_available is False
            and time.monotonic() - self._proxy_redis_last_failure
            < _PROXY_REDIS_FAILURE_BACKOFF_SECONDS
        ):
            return None

        timeout = self._proxy_redis_connect_timeout()
        try:
            client = aioredis.from_url(
                config.REDIS_APP_URL,
                decode_responses=True,
                socket_connect_timeout=timeout,
                socket_timeout=timeout,
            )
            await client.ping()
            self._proxy_redis_client = client
            self._proxy_redis_available = True
            return client
        except Exception as exc:
            logger.warning(
                "XActions proxy binding could not connect to Redis at %s: %s",
                config.REDIS_APP_URL,
                exc,
            )
            self._proxy_redis_available = False
            self._proxy_redis_last_failure = time.monotonic()
            return None

    async def bind_account_proxy(
        self, account_id: str, proxy_url: str
    ) -> None:
        """AD-SOC-3: Sticky 1-to-1 proxy mapping per platform account."""
        if not account_id or not isinstance(account_id, str):
            raise ValueError("account_id must be a non-empty string")
        self._account_proxies[account_id] = proxy_url

        client = await self._get_proxy_redis_client()
        if client:
            try:
                await client.hset(
                    XACTIONS_PROXY_REDIS_KEY, account_id, proxy_url
                )
            except Exception as exc:
                logger.warning(
                    "Failed to persist proxy for %s to Redis: %s",
                    account_id,
                    exc,
                )

    async def get_account_proxy(self, account_id: str) -> str | None:
        """Return the proxy bound to account_id, falling back to the default proxy."""
        if not account_id:
            return self.default_proxy_url

        if account_id in self._account_proxies:
            return self._account_proxies[account_id]

        client = await self._get_proxy_redis_client()
        if client:
            try:
                proxy = await client.hget(
                    XACTIONS_PROXY_REDIS_KEY, account_id
                )
                if proxy:
                    self._account_proxies[account_id] = proxy
                    return proxy
            except Exception as exc:
                logger.warning(
                    "Failed to read proxy for %s from Redis: %s",
                    account_id,
                    exc,
                )

        return self.default_proxy_url

    def _parse_proxy_url(self, proxy_url: str) -> tuple[str, dict[str, str] | None]:
        """Parse a proxy URL into a proxy string and optional proxyAuth dict."""
        parsed = urlparse(proxy_url)
        scheme = parsed.scheme or "http"
        host = parsed.hostname
        if not host:
            return proxy_url, None

        port = parsed.port or (443 if scheme == "https" else 80)
        proxy = f"{scheme}://{host}:{port}"
        auth = None
        if parsed.username and parsed.password:
            auth = {"username": parsed.username, "password": parsed.password}
        return proxy, auth

    async def _browser_options_for_account(
        self, account_id: str | None
    ) -> dict[str, Any] | None:
        if account_id:
            proxy = await self.get_account_proxy(account_id)
        else:
            proxy = self.default_proxy_url
        if not proxy:
            return None

        proxy_str, auth = self._parse_proxy_url(proxy)
        options: dict[str, Any] = {"proxy": proxy_str}
        if auth:
            options["proxyAuth"] = auth
        return options

    def _facebook_auth_cookie(self, params: dict[str, Any]) -> dict[str, str]:
        auth_cookie = params.get("auth_cookie") or {}
        c_user = (
            auth_cookie.get("c_user")
            or os.getenv("XACTIONS_FACEBOOK_C_USER", "")
            or getattr(config, "XACTIONS_FACEBOOK_C_USER", "")
        )
        xs = (
            auth_cookie.get("xs")
            or os.getenv("XACTIONS_FACEBOOK_XS", "")
            or getattr(config, "XACTIONS_FACEBOOK_XS", "")
        )
        if not c_user or not xs:
            raise ValueError(
                "Facebook scraping requires an auth cookie with c_user and xs. "
                "Pass auth_cookie={'c_user': '...', 'xs': '...'} or set "
                "XACTIONS_FACEBOOK_C_USER and XACTIONS_FACEBOOK_XS."
            )
        return {"c_user": str(c_user), "xs": str(xs)}

    async def _build_mcp_tool_args(
        self,
        action: str,
        params: dict[str, Any],
        account_id: str | None,
    ) -> tuple[str, dict[str, Any]]:
        if action == "x_facebook_group_posts":
            group_id = params.get("group_id")
            if not group_id:
                raise ValueError("group_id is required for x_facebook_group_posts")

            group_id_str = str(group_id)
            url = (
                group_id_str
                if re.match(r"^https?://", group_id_str)
                else f"https://www.facebook.com/groups/{group_id_str}"
            )

            arguments: dict[str, Any] = {
                "url": url,
                "limit": int(params.get("limit", 20)),
                "dryRun": False,
                "authCookie": self._facebook_auth_cookie(params),
            }

            browser_options = await self._browser_options_for_account(account_id)
            if browser_options:
                arguments["browserOptions"] = browser_options

            return "x_facebook_group_posts", arguments

        if action == "x_search_tweets":
            query = params.get("query")
            if not query:
                raise ValueError("query is required for x_search_tweets")
            arguments = {
                "query": str(query),
                "limit": int(params.get("limit", 20)),
                "platform": "twitter",
            }
            browser_options = await self._browser_options_for_account(account_id)
            if browser_options:
                arguments["browserOptions"] = browser_options
            return "x_search_tweets", arguments

        raise ValueError(f"Unsupported XActions tool action: {action}")

    def _extract_tool_text(self, result: Any) -> str:
        pieces = []
        for content in getattr(result, "content", []):
            if getattr(content, "type", None) == "text":
                pieces.append(getattr(content, "text", "") or "")
            elif hasattr(content, "text"):
                pieces.append(content.text)
            else:
                pieces.append(str(content))
        return "\n".join(pieces).strip()

    def _extract_tool_result(self, result: Any) -> Any:
        text = self._extract_tool_text(result)
        if not text:
            return []
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "XActions MCP tool returned non-JSON text: %s",
                exc,
            )
            raise

    async def _call_mcp_tool(
        self,
        server_params: StdioServerParameters,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float,
    ) -> Any:
        init_timeout = min(10.0, timeout)

        try:
            async with (
                stdio_client(server=server_params) as (read, write),
                ClientSession(read, write) as session,
            ):
                await asyncio.wait_for(
                    session.initialize(),
                    timeout=init_timeout,
                )
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=timeout,
                )
        except TimeoutError:
            logger.warning(
                "XActions MCP tool %s timed out after %.1fs",
                tool_name,
                timeout,
            )
            raise

        if result.isError:
            text = self._extract_tool_text(result) or "unknown MCP error"
            raise XActionsMcpError(
                f"XActions MCP tool {tool_name} returned error: {text}"
            )

        return self._extract_tool_result(result)

    async def _execute_xactions_command(
        self,
        action: str,
        params: dict[str, Any],
        account_id: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute an XActions MCP tool and wrap the result for downstream mapping."""
        if timeout is None:
            timeout = self.default_timeout

        try:
            tool_name, arguments = await self._build_mcp_tool_args(
                action, params, account_id
            )
        except ValueError as exc:
            logger.warning(
                "Invalid XActions tool arguments for %s: %s",
                action,
                exc,
            )
            return {"success": False, "error": str(exc), "data": []}

        # Resolve server parameters before the call; this raises a clear error
        # if XActions is not configured so we do not silently return empty data.
        server_params = self._resolve_mcp_server_params()

        try:
            raw = await self._call_mcp_tool(
                server_params,
                tool_name,
                arguments,
                timeout=timeout,
            )
        except TimeoutError:
            return {
                "success": False,
                "error": f"XActions MCP tool {tool_name} timed out",
                "data": [],
            }
        except json.JSONDecodeError as exc:
            return {
                "success": False,
                "error": f"Invalid JSON from XActions MCP: {exc}",
                "data": [],
            }
        except XActionsMcpError as exc:
            return {"success": False, "error": str(exc), "data": []}
        except Exception as exc:
            logger.warning(
                "XActions MCP tool %s failed: %s",
                tool_name,
                exc,
                exc_info=True,
            )
            return {"success": False, "error": str(exc), "data": []}

        if action == "x_facebook_group_posts":
            if isinstance(raw, dict) and raw.get("note"):
                return {"success": False, "error": raw["note"], "data": []}
            return {
                "success": True,
                "data": raw if isinstance(raw, list) else [],
            }

        if action == "x_search_tweets":
            return {
                "success": True,
                "data": raw if isinstance(raw, list) else [],
            }

        return {"success": True, "data": raw}

    async def fetch_facebook_group_posts(
        self,
        group_id: str,
        limit: int = 20,
        account_id: str | None = None,
        proxy: str | None = None,
        auth_cookie: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> list[SocialPostData]:
        """Ingest raw Facebook group posts using XActions stealth session."""
        if proxy and account_id:
            await self.bind_account_proxy(account_id, proxy)

        payload = {
            "group_id": group_id,
            "limit": limit,
            "account_id": account_id,
            "auth_cookie": auth_cookie,
        }
        res = await self._execute_xactions_command(
            "x_facebook_group_posts",
            payload,
            account_id,
            timeout=timeout,
        )
        if not res.get("success"):
            raise XActionsMcpError(
                res.get("error") or "x_facebook_group_posts failed"
            )
        raw_items = res.get("data", []) if isinstance(res, dict) else []
        if not isinstance(raw_items, list):
            logger.warning(
                "XActions facebook group posts returned non-list data: %s",
                type(raw_items),
            )
            return []

        posts: list[SocialPostData] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue

            external_post_id = raw.get("id") or raw.get("post_id")
            if not external_post_id:
                logger.warning(
                    "Skipping Facebook post with missing id: %s",
                    raw,
                )
                continue

            pub_date = _parse_published_at(
                raw.get("timestamp") or raw.get("created_time")
            )

            author = raw.get("author") or {}
            if isinstance(author, dict):
                author_id = author.get("id")
                author_name = author.get("name")
                author_url = author.get("url") or author.get("author_url")
            else:
                author_id = raw.get("author_id")
                author_name = (
                    author if isinstance(author, str) else raw.get("author_name")
                )
                author_url = raw.get("author_url")

            media = raw.get("media") or {}
            media_urls: list[str] = []
            if isinstance(media, dict):
                media_urls = media.get("images") or []
            if not media_urls and raw.get("media_urls"):
                media_urls = raw["media_urls"]

            post_url = raw.get("url") or raw.get("post_url")

            posts.append(
                SocialPostData(
                    platform="facebook",
                    external_post_id=str(external_post_id),
                    author_id=str(author_id) if author_id else None,
                    author_name=author_name,
                    author_url=author_url,
                    post_url=post_url,
                    content=raw.get("text") or raw.get("content") or "",
                    reactions_count=_to_int(
                        raw.get("likes", 0) or raw.get("reactions_count", 0)
                    ),
                    comments_count=_to_int(
                        raw.get("comments", 0) or raw.get("comments_count", 0)
                    ),
                    shares_count=_to_int(
                        raw.get("shares", 0) or raw.get("shares_count", 0)
                    ),
                    media_urls=media_urls
                    if isinstance(media_urls, list)
                    else [],
                    published_at=pub_date,
                )
            )

        return posts

    async def search_tweets(
        self,
        query: str,
        limit: int = 20,
        account_id: str | None = None,
        proxy: str | None = None,
        timeout: float | None = None,
    ) -> list[SocialPostData]:
        """Ingest Twitter keyword search tweets using XActions."""
        if proxy and account_id:
            await self.bind_account_proxy(account_id, proxy)

        payload = {
            "query": query,
            "limit": limit,
            "account_id": account_id,
        }
        res = await self._execute_xactions_command(
            "x_search_tweets",
            payload,
            account_id,
            timeout=timeout,
        )
        if not res.get("success"):
            raise XActionsMcpError(
                res.get("error") or "x_search_tweets failed"
            )
        raw_items = res.get("data", []) if isinstance(res, dict) else []
        if not isinstance(raw_items, list):
            logger.warning(
                "XActions search tweets returned non-list data: %s",
                type(raw_items),
            )
            return []

        posts: list[SocialPostData] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue

            external_post_id = raw.get("id_str") or raw.get("id")
            if not external_post_id:
                logger.warning(
                    "Skipping tweet with missing id: %s",
                    raw,
                )
                continue

            pub_date = _parse_published_at(
                raw.get("created_at") or raw.get("timestamp")
            )

            user = raw.get("user") or {}
            if isinstance(user, dict):
                author_id = user.get("id_str") or user.get("id")
                author_name = user.get("name")
                screen_name = user.get("screen_name") or user.get("username")
            else:
                author_id = raw.get("author_id")
                author_name = raw.get("author_name")
                screen_name = None

            if not author_name:
                author_name = raw.get("author")

            author_url = None
            if screen_name:
                author_url = f"https://x.com/{screen_name}"
            elif isinstance(author_name, str) and author_name:
                author_url = f"https://x.com/{author_name.lstrip('@')}"

            post_url = (
                raw.get("post_url") or raw.get("url") or raw.get("permalink")
            )

            posts.append(
                SocialPostData(
                    platform="twitter",
                    external_post_id=str(external_post_id),
                    author_id=str(author_id) if author_id else None,
                    author_name=author_name,
                    author_url=author_url,
                    post_url=post_url,
                    content=raw.get("full_text")
                    or raw.get("text")
                    or raw.get("content")
                    or "",
                    reactions_count=_to_int(
                        raw.get("favorite_count", 0)
                        or raw.get("reactions_count", 0)
                        or raw.get("likes", 0)
                    ),
                    comments_count=_to_int(
                        raw.get("reply_count", 0)
                        or raw.get("comments_count", 0)
                    ),
                    shares_count=_to_int(
                        raw.get("retweet_count", 0)
                        or raw.get("shares_count", 0)
                    ),
                    media_urls=raw.get("media_urls") or [],
                    published_at=pub_date,
                )
            )

        return posts

    async def ingest_raw_post_to_stream(
        self,
        post: SocialPostData,
        redis_client: Any | None = None,
    ) -> str:
        """AD-SOC-4: Push ingested social post to Redis Stream 'stream:social:raw_posts'."""
        created_locally = redis_client is None
        if created_locally:
            try:
                redis_client = aioredis.from_url(
                    config.REDIS_APP_URL, decode_responses=True
                )
                await redis_client.ping()
            except Exception as exc:
                raise RuntimeError(
                    f"Redis connection failed at {config.REDIS_APP_URL}: {exc}"
                ) from exc

        payload = {
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
            "published_at": post.published_at.isoformat()
            if post.published_at
            else "",
            "media_urls": json.dumps(post.media_urls or []),
        }

        if post.target_id is not None:
            payload["target_id"] = str(post.target_id)
        if post.workspace_id is not None:
            payload["workspace_id"] = str(post.workspace_id)

        try:
            msg_id = await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload)
        except Exception as exc:
            raise RuntimeError(
                f"Redis xadd failed on {STREAM_SOCIAL_RAW_POSTS}: {exc}"
            ) from exc
        finally:
            if created_locally:
                await redis_client.aclose()

        return msg_id

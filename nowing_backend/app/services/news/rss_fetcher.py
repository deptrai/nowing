"""RSS feed fetcher and parser for Vietnamese news portals."""

from __future__ import annotations

import asyncio
import html
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.utils.validators import validate_rss_feed_url

logger = logging.getLogger(__name__)

# Short timeout so a slow portal does not block the whole polling cycle.
_FEED_TIMEOUT = 10.0

# Ceiling on a single feed body; protects workers from oversized feeds.
_FEED_MAX_BYTES = 20 * 1024 * 1024

# Ceiling on items per feed; protects the polling cycle from huge rolling feeds.
_FEED_MAX_ITEMS = 1000

# Retry transient failures: network blips, 5xx, and 429 rate limits.
_FEED_RETRY_ATTEMPTS = 3
_FEED_RETRY_BACKOFF = 1.0

# Deterministic sentinel for items without a usable publication date.
_MISSING_PUB_DATE = datetime(1970, 1, 1, tzinfo=UTC)

# Some Vietnamese portals publish naive local times (e.g. Tuổi Trẻ uses
# "8/13/2026 8:06:00 PM" with no timezone). Only stamp UTC+7 on feeds from
# those known domains; any other feed with a naive US-format date is treated
# as UTC so we never silently shift other portals by seven hours.
_VN_TZ = timezone(timedelta(hours=7))
_VN_TZ_DOMAINS = {"tuoitre.vn"}

# Many portals return 403/429 to bare httpx default User-Agent strings.
_FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NowingRSS/1.0; +https://nowing.net)",
}


def _strip_html(raw: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_pub_date(raw: str | None, *, tz_hint: timezone | None = None) -> str:
    """Parse an RFC 822 / ISO 8601 pubDate and return an ISO 8601 UTC string.

    ``tz_hint`` stamps naive US-format dates (e.g. Tuổi Trẻ) with a local
    timezone; without it naive dates are interpreted as UTC.
    """
    if not raw:
        return _MISSING_PUB_DATE.isoformat()
    raw = raw.strip()
    normalized = raw.replace("\u202f", " ").replace("\u00a0", " ")

    # ISO 8601 (Atom <published>/<updated>, dc:date). parsedate_to_datetime
    # rejects ISO 8601 on Python 3.12, so try fromisoformat first.
    try:
        dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    except ValueError:
        pass

    try:
        dt = parsedate_to_datetime(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    except (TypeError, ValueError):
        pass

    # Tuổi Trẻ emits "M/d/yyyy h:mm:ss AM/PM" (naive local VN time, with a
    # U+202F narrow no-break space before the meridiem). Try a few US-format
    # variants before giving up; tolerate missing seconds and 2-digit years.
    tz = tz_hint or UTC
    for fmt in (
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %I:%M:%S %p",
    ):
        try:
            dt = datetime.strptime(normalized, fmt)
            return dt.replace(tzinfo=tz).astimezone(UTC).isoformat()
        except ValueError:
            continue

    logger.debug("Could not parse pubDate %r; using epoch sentinel", raw)
    return _MISSING_PUB_DATE.isoformat()


def _first_text(parent: Any, *tags: str) -> str | None:
    """Return text from the first matching child element (ignores XML namespaces).

    itertext() joins nested element text, so inline markup inside <title>
    or <description> is preserved instead of silently dropping the value.
    """
    for tag in tags:
        child = parent.find(f"{{*}}{tag}")
        if child is not None:
            text = "".join(child.itertext()).strip()
            if text:
                return text
    return None


def _first_category(item: Any) -> str | None:
    """Return the item category, honouring RSS 2.0 text and Atom term attr."""
    category = _first_text(item, "category")
    if category:
        return category
    category_el = item.find("{*}category")
    if category_el is not None:
        term = (category_el.get("term") or "").strip()
        if term:
            return term
    return None


def _extract_link(item: Any, feed_url: str) -> str:
    """Extract the article URL from an item/entry.

    Resolves relative URLs against the feed URL, prefers rel="alternate"/
    "canonical" Atom links, skips links that point back at the feed itself
    (rel="self" href equal to the feed URL), and falls back to a
    ``<guid isPermaLink="true">`` permalink when no usable ``<link>`` is present.
    """
    feed_normalized = _normalize_url(feed_url)

    # RSS 2.0 text <link> (may be relative).
    text = _first_text(item, "link")
    if text:
        resolved = _resolve_article_url(text, feed_url)
        if resolved and _normalize_url(resolved) != feed_normalized:
            return resolved

    # Atom <link href="..." rel="..."/>.
    links = item.findall("{*}link")
    fallback: str | None = None
    for link_el in links:
        href = (link_el.get("href") or "").strip()
        if not href:
            continue
        resolved = _resolve_article_url(href, feed_url)
        if not resolved or _normalize_url(resolved) == feed_normalized:
            continue
        rel = (link_el.get("rel") or "alternate").lower()
        if rel in ("alternate", "canonical", "self"):
            return resolved
        if fallback is None:
            fallback = resolved

    if fallback:
        return fallback

    # RSS 2.0 <guid isPermaLink="true"> fallback.
    guid_el = item.find("{*}guid")
    if guid_el is not None:
        is_permalink = (guid_el.get("isPermaLink") or "true").lower() != "false"
        guid_text = (guid_el.text or "").strip()
        if is_permalink and guid_text:
            resolved = _resolve_article_url(guid_text, feed_url)
            if resolved and _normalize_url(resolved) != feed_normalized:
                return resolved

    return ""


def _normalize_url(url: str) -> str:
    """Normalize a URL for identity comparisons (scheme/host/path only)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{host}{path}"


def _resolve_article_url(url: str, feed_url: str) -> str | None:
    """Resolve a possibly-relative article URL against the feed URL.

    Returns ``None`` if the result is not an http(s) URL or is just a fragment.
    """
    if not url:
        return None
    url = url.strip()
    if url.startswith("#"):
        return None
    try:
        resolved = urljoin(feed_url, url)
        parsed = urlparse(resolved)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    return resolved


@dataclass
class NewsArticle:
    """One parsed RSS news item."""

    title: str
    link: str
    description: str
    pub_date: str
    category: str | None
    source: str


async def _check_dns_ssrf(url: str) -> None:
    """Reject hostnames that resolve to private or loopback addresses.

    The literal validator only checks the hostname string; wildcard DNS
    services (nip.io, sslip.io, localtest.me, ...) map arbitrary names to
    internal IPs, so resolve every address at request time and require each
    one to be global. Resolution failures fail closed.
    """
    hostname = urlparse(url).hostname
    if not hostname:
        raise ValueError("RSS feed URL must have a host")

    try:
        infos = await asyncio.wait_for(
            asyncio.to_thread(socket.getaddrinfo, hostname, None),
            timeout=_FEED_TIMEOUT,
        )
    except TimeoutError as exc:
        raise ValueError(f"RSS feed host {hostname} DNS resolution timed out") from exc
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve RSS feed host {hostname}: {exc}") from exc

    addresses = [info[4][0] for info in infos]
    if not addresses:
        raise ValueError(f"Could not resolve RSS feed host {hostname}")

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if not ip.is_global:
            raise ValueError(
                f"RSS feed host {hostname} resolves to non-public address {address}"
            )


async def _validate_rss_request(request: httpx.Request) -> None:
    """Reject private/internal URLs before any request (including redirects)."""
    validate_rss_feed_url(str(request.url))
    await _check_dns_ssrf(str(request.url))


async def fetch_feed(url: str) -> list[NewsArticle]:
    """Fetch and parse a single RSS feed URL.

    Returns an empty list on network, parse, or validation failures so that
    one bad feed does not abort the entire poll.
    """
    try:
        validate_rss_feed_url(url)
    except ValueError as exc:
        logger.warning("RSS feed URL %s rejected: %s", url, exc)
        return []

    for attempt in range(_FEED_RETRY_ATTEMPTS):
        try:
            async with httpx.AsyncClient(
                timeout=_FEED_TIMEOUT,
                follow_redirects=True,
                headers=_FEED_HEADERS,
                event_hooks={"request": [_validate_rss_request]},
            ) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > _FEED_MAX_BYTES:
                            logger.warning(
                                "RSS feed %s exceeds %d bytes; skipping",
                                url,
                                _FEED_MAX_BYTES,
                            )
                            return []
                        chunks.append(chunk)
                body = b"".join(chunks)
                if not body:
                    logger.warning("RSS feed %s returned HTTP 200 with empty body", url)
                    return []
                break
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            is_retryable = status is not None and (status == 429 or status >= 500)
            if not is_retryable or attempt == _FEED_RETRY_ATTEMPTS - 1:
                logger.warning("RSS feed %s returned %s", url, status)
                return []
            wait = _FEED_RETRY_BACKOFF * (2**attempt)
            logger.warning(
                "RSS feed %s returned %s (attempt %d/%d); retrying in %.1fs",
                url,
                status,
                attempt + 1,
                _FEED_RETRY_ATTEMPTS,
                wait,
            )
            await asyncio.sleep(wait)
        except httpx.RequestError as exc:
            if attempt == _FEED_RETRY_ATTEMPTS - 1:
                logger.warning("RSS feed %s request error: %s", url, exc)
                return []
            wait = _FEED_RETRY_BACKOFF * (2**attempt)
            logger.warning(
                "RSS feed %s request error (attempt %d/%d); retrying in %.1fs",
                url,
                attempt + 1,
                _FEED_RETRY_ATTEMPTS,
                wait,
            )
            await asyncio.sleep(wait)
        except ValueError as exc:
            logger.warning("RSS feed URL %s rejected during request: %s", url, exc)
            return []

    # Reject entity-expansion (billion laughs) payloads before parsing.
    head = body[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in head:
        logger.warning("RSS feed %s declares DOCTYPE/ENTITY; skipping", url)
        return []

    try:
        # XML parsers can be picky; use the standard library and recover from
        # minor feed quirks rather than introducing a new dependency. Parsing
        # raw bytes lets ElementTree honour the XML prolog encoding (UTF-16
        # feeds are otherwise mis-decoded as str).
        import xml.etree.ElementTree as ET

        root = ET.fromstring(body)
    except ET.ParseError as exc:
        logger.warning("RSS feed %s parse error: %s", url, exc)
        return []

    channel = root.find("{*}channel")
    if channel is None:
        # Some feeds (e.g. Atom-style) use <feed> as the root; try first item.
        channel = root

    channel_title = _first_text(channel, "title")
    from .rss_config import source_name_from_url

    source_name = source_name_from_url(url, channel_title)

    host = (urlparse(url).hostname or "").lower()
    tz_hint = _VN_TZ if host in _VN_TZ_DOMAINS else None

    # RSS 2.0 <item>; Atom uses <entry>. {*}
    # ignores default/prefixed namespaces so all feed variants are found.
    items = (
        channel.findall("{*}item")
        or channel.findall("{*}entry")
        or root.findall(".//{*}item")
        or root.findall(".//{*}entry")
    )

    articles: list[NewsArticle] = []
    for item in items:
        if len(articles) >= _FEED_MAX_ITEMS:
            logger.warning(
                "RSS feed %s has more than %d items; truncating to first %d",
                url,
                _FEED_MAX_ITEMS,
                _FEED_MAX_ITEMS,
            )
            break
        title = _first_text(item, "title") or "Untitled"
        link = _extract_link(item, url)

        description = _strip_html(
            _first_text(item, "description") or _first_text(item, "summary") or ""
        )
        if not description:
            # Fall back to the title as searchable text rather than leaving empty.
            description = title

        pub_date = _parse_pub_date(
            _first_text(item, "pubDate")
            or _first_text(item, "published")
            or _first_text(item, "updated")
            or _first_text(item, "date"),
            tz_hint=tz_hint,
        )
        category = _first_category(item)

        articles.append(
            NewsArticle(
                title=title,
                link=link,
                description=description,
                pub_date=pub_date,
                category=category,
                source=source_name,
            )
        )

    logger.info("Fetched %d articles from %s", len(articles), url)
    return articles

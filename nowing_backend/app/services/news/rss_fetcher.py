"""RSS feed fetcher and parser for Vietnamese news portals."""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Short timeout so a slow portal does not block the whole polling cycle.
_FEED_TIMEOUT = 10.0


def _strip_html(raw: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_pub_date(raw: str | None) -> str:
    """Parse an RFC 822-ish pubDate and return an ISO 8601 UTC string."""
    if not raw:
        return datetime.now(UTC).isoformat()
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    except (TypeError, ValueError):
        logger.debug("Could not parse pubDate %r; using now", raw)
        return datetime.now(UTC).isoformat()


def _first_text(parent: Any, *tags: str) -> str | None:
    """Return text from the first matching child element."""
    for tag in tags:
        child = parent.find(tag)
        if child is not None and child.text:
            return child.text.strip()
    return None


@dataclass
class NewsArticle:
    """One parsed RSS news item."""

    title: str
    link: str
    description: str
    pub_date: str
    category: str | None
    source: str


async def fetch_feed(url: str) -> list[NewsArticle]:
    """Fetch and parse a single RSS feed URL.

    Returns an empty list on network or parse failures so that one bad
    feed does not abort the entire poll.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_FEED_TIMEOUT, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            body = response.text
    except httpx.HTTPStatusError as exc:
        logger.warning("RSS feed %s returned %s", url, exc.response.status_code)
        return []
    except httpx.RequestError as exc:
        logger.warning("RSS feed %s request error: %s", url, exc)
        return []

    try:
        # XML parsers can be picky; use the standard library and recover from
        # minor feed quirks rather than introducing a new dependency.
        import xml.etree.ElementTree as ET

        root = ET.fromstring(body)
    except ET.ParseError as exc:
        logger.warning("RSS feed %s parse error: %s", url, exc)
        return []

    channel = root.find("channel")
    if channel is None:
        # Some feeds (e.g. Atom-style) use <feed> as the root; try first item.
        channel = root

    channel_title = _first_text(channel, "title")
    from .rss_config import source_name_from_url

    source_name = source_name_from_url(url, channel_title)

    # RSS 2.0 <item>; Atom uses <entry>. Both are fine for a broad search.
    items = (
        channel.findall("item")
        or channel.findall("entry")
        or root.findall(".//item")
        or root.findall(".//entry")
    )

    articles: list[NewsArticle] = []
    for item in items:
        title = _first_text(item, "title") or "Untitled"
        link = _first_text(item, "link") or ""
        if not link:
            # Atom often places the href in a <link href="..."/> attribute.
            link_el = item.find("link")
            if link_el is not None:
                link = link_el.get("href") or ""

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
        )
        category = _first_text(item, "category")

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

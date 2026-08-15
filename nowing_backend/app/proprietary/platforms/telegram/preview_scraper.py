"""Stateless HTTP Web Preview scraper for public Telegram channels (Story 22.1 / AD-1, AD-2)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from selectolax.parser import HTMLParser, Node

from app.proprietary.platforms.telegram.entity_extractor import TelegramEntityExtractor
from app.proprietary.platforms.telegram.schemas import (
    TelegramChannelInfo,
    TelegramMessageParsed,
    TelegramScrapeResult,
)

logger = logging.getLogger(__name__)

# Modern Desktop User-Agents for stealth scraping
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]


def parse_count(raw: str | None) -> int:
    """Parse numeric strings with K/M multipliers (e.g. '25.4K' -> 25400)."""
    if not raw:
        return 0
    raw = raw.strip().upper().replace(",", "")
    if raw.endswith("K"):
        try:
            return int(float(raw[:-1]) * 1000)
        except ValueError:
            return 0
    elif raw.endswith("M"):
        try:
            return int(float(raw[:-1]) * 1000000)
        except ValueError:
            return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _extract_text_with_newlines(node: Node) -> str:
    """Extract text from HTML node while preserving line breaks from <br>."""
    # Replace <br> with newline in HTML
    html = node.html or ""
    # Simple regex conversion of <br> and <p> to newlines
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Unescape HTML entities
    import html as html_module
    text = html_module.unescape(text)
    return text.strip()


def parse_channel_info(html: str, username: str) -> TelegramChannelInfo:
    """Parse channel header info from preview HTML."""
    tree = HTMLParser(html)

    # Title
    title_node = tree.css_first(".tgme_channel_info_title, .tgme_page_title")
    title = title_node.text(strip=True) if title_node else username

    # Description
    desc_node = tree.css_first(".tgme_channel_info_description, .tgme_page_description")
    description = _extract_text_with_newlines(desc_node) if desc_node else ""

    # Avatar
    photo_node = tree.css_first(".tgme_page_photo img, .tgme_channel_info_header img")
    avatar_url = photo_node.attributes.get("src") if photo_node else None

    # Subscribers
    counter_node = tree.css_first(".tgme_channel_info_counter .counter_value, .tgme_page_extra")
    subscribers_count = 0
    if counter_node:
        counter_text = counter_node.text(strip=True)
        # Match digits with K/M
        match = re.search(r"([\d.,]+\s*[KM]?)", counter_text, re.IGNORECASE)
        if match:
            subscribers_count = parse_count(match.group(1))

    return TelegramChannelInfo(
        username=username.lstrip("@"),
        title=title,
        description=description,
        avatar_url=avatar_url,
        subscribers_count=subscribers_count,
        is_public=True,
    )


def parse_messages(html: str, channel_username: str) -> list[TelegramMessageParsed]:
    """Parse messages from preview HTML and enrich with NLP entities."""
    tree = HTMLParser(html)
    extractor = TelegramEntityExtractor()
    messages: list[TelegramMessageParsed] = []

    clean_username = channel_username.lstrip("@")
    wraps = tree.css(".tgme_widget_message_wrap, .tgme_widget_message")

    seen_ids = set()
    for wrap in wraps:
        msg_node = wrap.css_first(".tgme_widget_message") or wrap
        post_attr = msg_node.attributes.get("data-post") or wrap.attributes.get("data-post")

        if not post_attr:
            # Try to find link with post id
            date_link = msg_node.css_first(".tgme_widget_message_date")
            if date_link and date_link.attributes.get("href"):
                href = date_link.attributes["href"]
                post_attr = href.split("t.me/")[-1]

        if not post_attr or "/" not in post_attr:
            continue

        try:
            msg_id_str = post_attr.split("/")[-1]
            message_id = int(msg_id_str)
        except (ValueError, IndexError):
            continue

        if message_id in seen_ids:
            continue
        seen_ids.add(message_id)

        # Text content
        text_node = msg_node.css_first(".tgme_widget_message_text")
        text_content = _extract_text_with_newlines(text_node) if text_node else ""

        # Views count
        views_node = msg_node.css_first(".tgme_widget_message_views")
        views = parse_count(views_node.text(strip=True) if views_node else "0")

        # Forwards count
        forwards_node = msg_node.css_first(".tgme_widget_message_forwards")
        forwards = parse_count(forwards_node.text(strip=True) if forwards_node else "0")

        # Published date
        date_node = msg_node.css_first(".tgme_widget_message_date time")
        published_at = datetime.now(UTC)
        if date_node and date_node.attributes.get("datetime"):
            dt_str = date_node.attributes["datetime"]
            with contextlib.suppress(ValueError):
                published_at = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

        # Author name
        author_node = msg_node.css_first(".tgme_widget_message_owner_name, .tgme_widget_message_from_author")
        author_name = author_node.text(strip=True) if author_node else None

        # Media detection
        photo_nodes = msg_node.css(".tgme_widget_message_photo_wrap")
        video_nodes = msg_node.css(".tgme_widget_message_video_player, .tgme_widget_message_roundvideo")
        doc_nodes = msg_node.css(".tgme_widget_message_document")
        has_media = bool(photo_nodes or video_nodes or doc_nodes)

        media_urls: list[str] = []
        for p in photo_nodes:
            style = p.attributes.get("style", "")
            url_match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
            if url_match:
                media_urls.append(url_match.group(1))

        # NLP Entity Extraction & Intent Classification
        entities = extractor.extract(text_content)

        messages.append(
            TelegramMessageParsed(
                message_id=message_id,
                channel_username=clean_username,
                text=text_content,
                published_at=published_at,
                views=views,
                forwards=forwards,
                replies_count=0,
                has_media=has_media,
                media_urls=media_urls,
                author_name=author_name,
                intent_tag=entities.intent_tag,
                entities=entities,
            )
        )

    return messages


class TelegramWebPreviewScraper:
    """Stateless public preview scraper with connection pooling and retries."""

    def __init__(self, timeout: float = 15.0, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max_retries

    async def scrape_channel(
        self,
        channel_username: str,
        before: int | None = None,
        after: int | None = None,
    ) -> TelegramScrapeResult:
        """Scrape public Telegram channel messages via web preview (https://t.me/s/{channel})."""
        clean_username = channel_username.lstrip("@").strip()
        url = f"https://t.me/s/{clean_username}"
        params: dict[str, Any] = {}
        if before:
            params["before"] = before
        if after:
            params["after"] = after

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Referer": "https://t.me/",
        }

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            last_err = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await client.get(url, params=params, headers=headers)
                    if response.status_code == 200:
                        html = response.text
                        channel_info = parse_channel_info(html, clean_username)
                        messages = parse_messages(html, clean_username)
                        return TelegramScrapeResult(channel_info=channel_info, messages=messages)

                    if response.status_code == 404:
                        logger.warning("Telegram channel @%s not found (404)", clean_username)
                        return TelegramScrapeResult(
                            channel_info=TelegramChannelInfo(username=clean_username, title=clean_username),
                            messages=[],
                        )

                    if response.status_code in (429, 503):
                        backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                        logger.warning("Telegram rate limit (%d), backing off %.2fs (attempt %d)", response.status_code, backoff, attempt)
                        await asyncio.sleep(backoff)
                        continue

                    response.raise_for_status()
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    last_err = exc
                    backoff = (2 ** attempt) + random.uniform(0.1, 0.5)
                    await asyncio.sleep(backoff)

            logger.error("Failed to scrape Telegram channel @%s after %d retries: %s", clean_username, self.max_retries, last_err)
            return TelegramScrapeResult(
                channel_info=TelegramChannelInfo(username=clean_username, title=clean_username),
                messages=[],
            )

"""RSS news feed support for workspace knowledge bases."""

from .rss_config import DEFAULT_VIETNAMESE_FEEDS, get_feeds_for_workspace
from .rss_fetcher import NewsArticle, fetch_feed

__all__ = [
    "DEFAULT_VIETNAMESE_FEEDS",
    "NewsArticle",
    "fetch_feed",
    "get_feeds_for_workspace",
]

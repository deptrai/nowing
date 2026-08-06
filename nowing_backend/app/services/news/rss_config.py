"""Default Vietnamese RSS feed configuration and per-workspace override support."""

from urllib.parse import urlparse

# ponytail: hardcoded default Vietnamese news feeds for the first release.
# Admins can override via the connector's `config.feed_urls` JSON field.
DEFAULT_VIETNAMESE_FEEDS: list[str] = [
    "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "https://tuoitre.vn/rss/thoi-su.rss",
    "https://dantri.com.vn/rss/tin-moi-nhat.rss",
    "https://vietnamnet.vn/rss/tin-moi-nhat.rss",
]


def get_feeds_for_workspace(connector_config: dict | None) -> list[str]:
    """Return feed URLs for a workspace, honouring optional connector overrides."""
    if connector_config and connector_config.get("feed_urls"):
        return list(connector_config["feed_urls"])
    return list(DEFAULT_VIETNAMESE_FEEDS)


def source_name_from_url(url: str, channel_title: str | None = None) -> str:
    """Derive a short source name from the feed URL domain or channel title."""
    if channel_title:
        return channel_title.strip()
    parsed = urlparse(url)
    return (parsed.hostname or "unknown").replace("www.", "")

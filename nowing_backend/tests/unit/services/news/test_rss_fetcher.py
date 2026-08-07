"""Unit tests for the RSS feed fetcher/parser."""

from __future__ import annotations

import pytest

from app.services.news.rss_fetcher import NewsArticle, _parse_pub_date, fetch_feed

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>VnExpress</title>
    <link>https://vnexpress.net</link>
    <description>VnExpress tin tức</description>
    <item>
      <title>Heavy rain causes flooding in Hanoi</title>
      <link>https://vnexpress.net/article/1</link>
      <description>&lt;p&gt;Authorities issued warnings as streets flooded.&lt;/p&gt;</description>
      <pubDate>Mon, 05 Aug 2024 14:30:00 GMT</pubDate>
      <category>Weather</category>
    </item>
    <item>
      <title> Vietnam economy grows 6.5% in 2024</title>
      <link>https://vnexpress.net/article/2</link>
      <description>&lt;p&gt;GDP expansion beat expectations, officials said.&lt;/p&gt;</description>
      <pubDate>Tue, 06 Aug 2024 08:00:00 GMT</pubDate>
      <category>Economy</category>
    </item>
  </channel>
</rss>
"""


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.mark.unit
async def test_fetch_feed_parses_required_fields(monkeypatch):
    """Each item is parsed into a NewsArticle with title, link, description, pubDate, category and source."""

    async def _fake_get(self, url):
        return _FakeResponse(SAMPLE_RSS)

    monkeypatch.setattr(
        "app.services.news.rss_fetcher.httpx.AsyncClient.get", _fake_get
    )

    articles = await fetch_feed("https://vnexpress.net/rss/tin-moi-nhat.rss")

    assert len(articles) == 2
    first = articles[0]
    assert first.title == "Heavy rain causes flooding in Hanoi"
    assert first.link == "https://vnexpress.net/article/1"
    assert "flood" in first.description.lower()
    assert first.description == "Authorities issued warnings as streets flooded."
    assert first.category == "Weather"
    assert first.source == "VnExpress"
    assert first.pub_date.endswith("+00:00")

    second = articles[1]
    assert second.title == "Vietnam economy grows 6.5% in 2024"
    assert second.link == "https://vnexpress.net/article/2"
    assert second.category == "Economy"


@pytest.mark.unit
async def test_fetch_feed_empty_items(monkeypatch):
    """Empty RSS feeds return an empty article list."""
    empty_rss = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>
"""

    async def _fake_get(self, url):
        return _FakeResponse(empty_rss)

    monkeypatch.setattr(
        "app.services.news.rss_fetcher.httpx.AsyncClient.get", _fake_get
    )
    articles = await fetch_feed("https://empty.example/feed.rss")
    assert articles == []


@pytest.mark.unit
async def test_fetch_feed_http_error(monkeypatch):
    """HTTP errors are handled gracefully and return an empty list."""
    import httpx

    async def _fake_get(self, url):
        raise httpx.RequestError(
            "Server error",
            request=httpx.Request("GET", "https://bad.example/feed.rss"),
        )

    monkeypatch.setattr(
        "app.services.news.rss_fetcher.httpx.AsyncClient.get", _fake_get
    )
    articles = await fetch_feed("https://bad.example/feed.rss")
    assert articles == []


ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom</title>
  <entry>
    <title>Atom Entry</title>
    <link href="https://example.com/article/1"/>
    <summary>Atom summary</summary>
    <updated>2024-08-06T00:00:00Z</updated>
  </entry>
</feed>
"""


@pytest.mark.unit
async def test_news_article_dataclass():
    """NewsArticle stores the expected fields."""
    article = NewsArticle(
        title="T",
        link="https://example.com/a",
        description="D",
        pub_date="2024-08-06T00:00:00+00:00",
        category="C",
        source="S",
    )
    assert article.title == "T"
    assert article.link == "https://example.com/a"
    assert article.description == "D"
    assert article.category == "C"
    assert article.source == "S"


@pytest.mark.unit
async def test_fetch_feed_parses_atom_with_namespace(monkeypatch):
    """Atom feeds with a default namespace are found and parsed."""

    async def _fake_get(self, url):
        return _FakeResponse(ATOM_FEED)

    monkeypatch.setattr(
        "app.services.news.rss_fetcher.httpx.AsyncClient.get", _fake_get
    )
    articles = await fetch_feed("https://example.com/feed.atom")

    assert len(articles) == 1
    assert articles[0].title == "Atom Entry"
    assert articles[0].link == "https://example.com/article/1"
    assert articles[0].pub_date.endswith("+00:00")


@pytest.mark.unit
async def test_fetch_feed_rejects_private_ip():
    """Private/internal feed URLs are rejected before any network call."""
    articles = await fetch_feed("http://192.168.1.1/feed.rss")
    assert articles == []


@pytest.mark.unit
async def test_parse_pub_date_invalid_uses_epoch():
    """Unparseable pubDate falls back to a deterministic epoch sentinel."""
    assert _parse_pub_date("not a date") == "1970-01-01T00:00:00+00:00"
    assert _parse_pub_date(None) == "1970-01-01T00:00:00+00:00"

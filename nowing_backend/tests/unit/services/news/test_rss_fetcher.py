"""Unit tests for the RSS feed fetcher/parser."""

from __future__ import annotations

import pytest

from app.services.news.rss_config import (
    DEFAULT_VIETNAMESE_FEEDS,
    get_feeds_for_workspace,
)
from app.services.news.rss_fetcher import (
    _MISSING_PUB_DATE,
    NewsArticle,
    _parse_pub_date,
    fetch_feed,
)

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
    def __init__(self, content: bytes | str, status_code: int = 200):
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    async def aiter_bytes(self):
        for i in range(0, len(self.content), 1024):
            yield self.content[i : i + 1024]


class _FakeStream:
    def __init__(self, response: _FakeResponse):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *exc):
        return False


def _patch_fetch(monkeypatch, content: bytes | str, status_code: int = 200):
    """Patch httpx streaming GET + disable DNS SSRF resolution for unit tests."""

    def _fake_stream(self, method, url, **kwargs):
        return _FakeStream(_FakeResponse(content, status_code))

    async def _no_dns_check(url):
        return None

    monkeypatch.setattr(
        "app.services.news.rss_fetcher.httpx.AsyncClient.stream", _fake_stream
    )
    monkeypatch.setattr("app.services.news.rss_fetcher._check_dns_ssrf", _no_dns_check)
    monkeypatch.setattr("app.services.news.rss_fetcher._check_dns_ssrf", _no_dns_check)


@pytest.mark.unit
async def test_fetch_feed_parses_required_fields(monkeypatch):
    """Each item is parsed into a NewsArticle with title, link, description, pubDate, category and source."""
    _patch_fetch(monkeypatch, SAMPLE_RSS)

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
    _patch_fetch(monkeypatch, empty_rss)
    articles = await fetch_feed("https://empty.example/feed.rss")
    assert articles == []


@pytest.mark.unit
async def test_fetch_feed_http_error(monkeypatch):
    """HTTP errors are handled gracefully and return an empty list."""
    import httpx

    def _fake_stream(self, method, url, **kwargs):
        raise httpx.RequestError(
            "Server error",
            request=httpx.Request("GET", "https://bad.example/feed.rss"),
        )

    monkeypatch.setattr(
        "app.services.news.rss_fetcher.httpx.AsyncClient.stream", _fake_stream
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
    _patch_fetch(monkeypatch, ATOM_FEED)
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


@pytest.mark.unit
async def test_parse_pub_date_tuoitre_naive_local_format():
    """Tuổi Trẻ emits 'M/d/yyyy h:mm:ss AM/PM' with U+202F — must not fall back to epoch."""
    from app.services.news.rss_fetcher import _VN_TZ

    assert (
        _parse_pub_date("8/13/2026 8:06:00\u202fPM", tz_hint=_VN_TZ)
        == "2026-08-13T13:06:00+00:00"
    )
    assert (
        _parse_pub_date("8/13/2026 7:57:00\u202fAM", tz_hint=_VN_TZ)
        == "2026-08-13T00:57:00+00:00"
    )
    # non-breaking space variant too
    assert (
        _parse_pub_date("8/13/2026 10:53:00\u00a0PM", tz_hint=_VN_TZ)
        == "2026-08-13T15:53:00+00:00"
    )


@pytest.mark.unit
async def test_parse_pub_date_iso_8601_atom():
    """Atom ISO 8601 dates parse via fromisoformat instead of falling back to epoch."""
    assert _parse_pub_date("2024-08-06T00:00:00Z") == "2024-08-06T00:00:00+00:00"
    assert _parse_pub_date("2024-08-06T07:30:00+07:00") == "2024-08-06T00:30:00+00:00"
    assert (
        _parse_pub_date("2024-08-06T00:00:00.123+00:00")
        == "2024-08-06T00:00:00.123000+00:00"
    )


@pytest.mark.unit
async def test_parse_pub_date_naive_without_hint_is_utc():
    """Naive US-format dates without a VN tz_hint are UTC, not silently +7h."""
    assert _parse_pub_date("8/13/2026 8:06:00 PM") == "2026-08-13T20:06:00+00:00"


@pytest.mark.unit
async def test_parse_pub_date_partial_formats():
    """Partial US-format variants (no seconds, 2-digit year) still parse."""
    from app.services.news.rss_fetcher import _VN_TZ

    assert (
        _parse_pub_date("8/13/2026 8:06 PM", tz_hint=_VN_TZ)
        == "2026-08-13T13:06:00+00:00"
    )
    assert (
        _parse_pub_date("8/13/26 8:06:00 PM", tz_hint=_VN_TZ)
        == "2026-08-13T13:06:00+00:00"
    )


@pytest.mark.unit
async def test_fetch_feed_atom_self_link_does_not_collapse(monkeypatch):
    """Atom entries whose first <link> is rel="self" pointing at the feed must
    still resolve to their real article URL instead of collapsing the feed."""
    atom_self_link = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Self Link Feed</title>
  <link href="https://example.com/feed.atom" rel="self"/>
  <entry>
    <title>First</title>
    <link href="https://example.com/feed.atom" rel="self"/>
    <link href="https://example.com/article/1" rel="alternate"/>
    <updated>2024-08-06T00:00:00Z</updated>
  </entry>
  <entry>
    <title>Second</title>
    <link href="https://example.com/feed.atom" rel="self"/>
    <link href="https://example.com/article/2" rel="alternate"/>
    <updated>2024-08-06T00:00:00Z</updated>
  </entry>
</feed>
"""
    _patch_fetch(monkeypatch, atom_self_link)
    articles = await fetch_feed("https://example.com/feed.atom")

    assert len(articles) == 2
    assert articles[0].link == "https://example.com/article/1"
    assert articles[1].link == "https://example.com/article/2"


@pytest.mark.unit
async def test_fetch_feed_atom_category_term(monkeypatch):
    """Atom <category term="..."/> is honoured for the article category."""
    atom_category = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Category Feed</title>
  <entry>
    <title>Entry</title>
    <link href="https://example.com/article/1"/>
    <category term="Politics"/>
    <updated>2024-08-06T00:00:00Z</updated>
  </entry>
</feed>
"""
    _patch_fetch(monkeypatch, atom_category)
    articles = await fetch_feed("https://example.com/feed.atom")
    assert articles[0].category == "Politics"


@pytest.mark.unit
async def test_fetch_feed_inline_markup_title(monkeypatch):
    """Inline markup inside <title> is joined via itertext instead of 'Untitled'."""
    inline = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
  <item>
    <title><![CDATA[<b>Bold</b> headline]]></title>
    <link>https://example.com/a</link>
  </item>
</channel></rss>
"""
    _patch_fetch(monkeypatch, inline)
    articles = await fetch_feed("https://example.com/feed.rss")
    assert articles[0].title == "<b>Bold</b> headline"


@pytest.mark.unit
async def test_fetch_feed_rejects_entity_expansion(monkeypatch):
    """Feeds declaring DOCTYPE/ENTITY (billion laughs) are rejected."""
    evil = """<?xml version="1.0"?>
<!DOCTYPE rss [<!ENTITY x "y">]>
<rss version="2.0"><channel><title>T</title></channel></rss>
"""
    _patch_fetch(monkeypatch, evil)
    articles = await fetch_feed("https://example.com/feed.rss")
    assert articles == []


@pytest.mark.unit
async def test_dns_ssrf_check_blocks_internal_resolution(monkeypatch):
    """Wildcard-DNS hostnames resolving to private IPs are rejected."""
    import socket

    from app.services.news.rss_fetcher import _check_dns_ssrf

    def _fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(
        "app.services.news.rss_fetcher.socket.getaddrinfo", _fake_getaddrinfo
    )
    with pytest.raises(ValueError, match="non-public"):
        await _check_dns_ssrf("http://169.254.169.254.nip.io/feed.rss")

    def _fake_getaddrinfo_public(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(
        "app.services.news.rss_fetcher.socket.getaddrinfo", _fake_getaddrinfo_public
    )
    await _check_dns_ssrf("http://example.com/feed.rss")


@pytest.mark.unit
async def test_dns_ssrf_check_fails_closed_on_resolution_error(monkeypatch):
    """Unresolvable hosts fail closed instead of passing the SSRF check."""
    import socket

    from app.services.news.rss_fetcher import _check_dns_ssrf

    def _fake_getaddrinfo_error(host, port):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(
        "app.services.news.rss_fetcher.socket.getaddrinfo", _fake_getaddrinfo_error
    )
    with pytest.raises(ValueError, match="Could not resolve"):
        await _check_dns_ssrf("http://unresolvable.example/feed.rss")


@pytest.mark.unit
def test_default_vietnamese_feeds():
    """The 4 default portal feeds are https URLs and non-empty."""
    assert len(DEFAULT_VIETNAMESE_FEEDS) == 4
    assert len(set(DEFAULT_VIETNAMESE_FEEDS)) == 4
    assert all(url.startswith("https://") for url in DEFAULT_VIETNAMESE_FEEDS)
    hosts = [url.split("/")[2] for url in DEFAULT_VIETNAMESE_FEEDS]
    assert "vnexpress.net" in hosts
    assert "tuoitre.vn" in hosts
    assert "dantri.com.vn" in hosts
    assert "vietnamnet.vn" in hosts


@pytest.mark.unit
def test_get_feeds_for_workspace_dedupes():
    """Duplicate or blank feed_urls in connector config are dropped, order kept."""
    feeds = get_feeds_for_workspace(
        {
            "feed_urls": [
                "https://a.example/rss",
                "https://a.example/rss",
                "  ",
                "https://b.example/rss",
            ]
        }
    )
    assert feeds == ["https://a.example/rss", "https://b.example/rss"]
    assert get_feeds_for_workspace(None) == DEFAULT_VIETNAMESE_FEEDS


@pytest.mark.unit
def test_news_fingerprint_nfc_normalisation():
    """Fingerprint merges NFC vs NFD titles and ignores whitespace churn."""
    from app.tasks.connector_indexers.rss_indexer import _news_fingerprint

    article = NewsArticle(
        title="Hà Nội  mưa lớn",
        link="https://a.example/x",
        description="",
        pub_date=_MISSING_PUB_DATE.isoformat(),
        category=None,
        source="S",
    )
    # NFD decomposition of "à"/"ội"/"ớn" + doubled space in title
    nfd_title = "Ha\u0300 No\u0302\u0323i  mu\u031ba lo\u031b\u0301n"
    article_nfd = NewsArticle(
        title=nfd_title,
        link="https://a.example/x",
        description="",
        pub_date=_MISSING_PUB_DATE.isoformat(),
        category=None,
        source="S",
    )
    assert _news_fingerprint(article) == _news_fingerprint(article_nfd)

    # description repeating the title does not change the fingerprint
    article_with_desc = NewsArticle(
        title="Hà Nội mưa lớn",
        link="https://a.example/x",
        description="Hà Nội mưa lớn",
        pub_date=_MISSING_PUB_DATE.isoformat(),
        category=None,
        source="S",
    )
    assert _news_fingerprint(article) == _news_fingerprint(article_with_desc)

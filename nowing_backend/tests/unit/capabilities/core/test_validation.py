"""Red-phase tests for the shared ``HttpUrlStr`` validator (Story 2.9 AC-1/AC-6).

These tests encode the EXPECTED contract and FAIL (collection error) until
``app/capabilities/core/validation.py`` is implemented — TDD red phase.

Contract decisions (from grill-me Q3/Q4, verified against ``validators.url``):
- The validator trims whitespace BEFORE validating (``validators.url`` does NOT trim).
- It accepts only ``http``/``https`` schemes (``validators.url`` accepts ``ftp``!).
- ``validators.url`` raises (does not return False) on malformed input -> wrap in try/except.
- ``localhost`` is rejected (``validators.url`` requires a dotted host); bare IPs are accepted.
- No normalization: trailing slash / query / fragment preserved.
- Generous length cap of 2048 chars (``validators.url`` has no cap of its own).
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.capabilities.core.validation import HttpUrlStr

pytestmark = pytest.mark.unit


class _UrlList(BaseModel):
    urls: list[HttpUrlStr]


def _errors(urls: list[object]) -> list[dict]:
    with pytest.raises(ValidationError) as exc_info:
        _UrlList(urls=urls)  # type: ignore[arg-type]
    return exc_info.value.errors()


# ---------------------------------------------------------------------------
# Accept cases (AC-1: pass through unchanged, no normalization)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://example.com", "https://example.com"),
        # trailing slash / query / fragment preserved (no normalization)
        ("https://example.com/a/b?q=1#frag", "https://example.com/a/b?q=1#frag"),
        ("http://example.com", "http://example.com"),
        # leading/trailing whitespace trimmed, still valid
        (" https://example.com ", "https://example.com"),
        # Amazon EU TLDs (story 2.8 downstream dependency)
        ("https://amazon.de/dp/B09V3KXJPB", "https://amazon.de/dp/B09V3KXJPB"),
        (
            "https://www.amazon.co.uk/dp/B09V3KXJPB",
            "https://www.amazon.co.uk/dp/B09V3KXJPB",
        ),
        ("https://amazon.fr/x", "https://amazon.fr/x"),
        # short-link hosts keep working
        ("https://youtu.be/abc123", "https://youtu.be/abc123"),
    ],
)
def test_accepts_http_urls(raw: str, expected: str) -> None:
    assert _UrlList(urls=[raw]).urls == [expected]


def test_accepts_bare_ip_host() -> None:
    # validators.url accepts dotted IP hosts; decision: keep them (server may
    # legitimately resolve to an IP that happens to be scrapeable).
    assert _UrlList(urls=["http://127.0.0.1:8080"]).urls == ["http://127.0.0.1:8080"]


# ---------------------------------------------------------------------------
# Reject cases (AC-1: malformed / non-http(s) URLs rejected before scraping)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "ftp://example.com",  # validators.url returns True for ftp -> scheme guard needed
        "javascript:alert(1)",
        "file:///etc/passwd",
        "not-a-url",
        "https://",  # scheme-only
        "http://",  # scheme-only
        "",
        "   ",  # whitespace-only after trim
    ],
)
def test_rejects_malformed_or_non_http_urls(raw: str) -> None:
    errors = _errors([raw])
    assert errors[0]["loc"] == ("urls", 0)


def test_rejects_localhost_without_tld() -> None:
    # Decision (grill-me Q3): follow validators.url — bare "localhost" has no
    # dotted host, so it is rejected. Same behavior as validate_url() in
    # app/utils/validators.py. The 127.0.0.1 form stays accepted (see above).
    with pytest.raises(ValidationError):
        _UrlList(urls=["http://localhost:8080"])


def test_rejects_urls_over_the_length_cap() -> None:
    with pytest.raises(ValidationError):
        _UrlList(urls=["https://example.com/" + "a" * 2050])


def test_accepts_url_exactly_at_the_length_cap() -> None:
    url = "https://example.com/" + "a" * (2048 - len("https://example.com/"))
    assert _UrlList(urls=[url]).urls == [url]


def test_rejects_none_in_list_position() -> None:
    with pytest.raises(ValidationError):
        _UrlList(urls=[None])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Error contract (AC-1 Pattern 5: exact upstream message)
# ---------------------------------------------------------------------------


def test_error_message_is_the_exact_upstream_phrase() -> None:
    errors = _errors(["ftp://example.com"])
    assert errors[0]["msg"] == "must be a valid http(s) URL"
    assert errors[0]["type"] == "http_url"

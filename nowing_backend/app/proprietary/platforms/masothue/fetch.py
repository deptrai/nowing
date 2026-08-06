"""Fetch search and detail pages from masothue.com."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any
from urllib.parse import urlencode, urljoin

from scrapling.fetchers import AsyncFetcher

from app.config import config
from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)

_ORIGIN = "https://masothue.com"


class MasothueRateLimitedError(RuntimeError):
    """Raised when masothue.com returns 429."""


class MasothueAccessBlockedError(RuntimeError):
    """Raised when masothue.com blocks access (403/Cloudflare)."""


class MasothueDecodeError(ValueError):
    """Raised when a page cannot be decoded as usable HTML."""


class MasothueTimeoutError(RuntimeError):
    """Raised when a request times out."""


def _headers() -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7",
        "Origin": _ORIGIN,
        "Referer": f"{_ORIGIN}/",
    }


def _search_url(query: str, search_type: str, page: int = 1) -> str:
    params: dict[str, Any] = {"q": query, "type": search_type}
    if page > 1:
        params["page"] = page
    return f"{_ORIGIN}/Search/?{urlencode(params)}"


def _status_for_url(status: int, url: str) -> None:
    if status == 429:
        raise MasothueRateLimitedError(f"{url} returned 429")
    if status in (403, 451):
        raise MasothueAccessBlockedError(f"{url} returned {status}")
    if status in (500, 502, 503, 504):
        raise MasothueAccessBlockedError(f"{url} returned {status}")


def _text(response: Any) -> str:
    if hasattr(response, "html_content") and response.html_content:
        return response.html_content
    if hasattr(response, "text"):
        return response.text
    body = response.body
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


def _looks_like_cloudflare(html: str) -> bool:
    markers = [
        "cf-browser-verification",
        "challenge-form",
        "Just a moment",
        "Checking your browser",
        "__cf_bm",
        "cf-challenge",
    ]
    lower = html.lower()
    return any(marker.lower() in lower for marker in markers)


async def fetch_search_page(
    query: str,
    search_type: str = "auto",
    page: int = 1,
    *,
    fetch_fn: Any | None = None,
) -> tuple[str, int]:
    """Fetch the masothue.com search results page and return (html, status).

    A 302 redirect to a detail page is converted to a detail fetch, because an
    exact tax-code match returns the company page directly.
    """
    url = _search_url(query, search_type, page)
    fetch = fetch_fn or AsyncFetcher.get

    try:
        response = await fetch(
            url,
            headers=_headers(),
            proxy=get_proxy_url(),
            stealthy_headers=True,
            timeout=getattr(config, "MASOTHUE_TIMEOUT_S", 30.0),
            follow_redirects=False,
        )
    except TimeoutError as exc:
        raise MasothueTimeoutError(f"timeout for {url}") from exc
    except Exception as exc:
        raise MasothueAccessBlockedError(f"{url} fetch failed: {exc}") from exc

    status = getattr(response, "status", 0)

    # Exact match: server sends 302 to a detail path like /<mst>-<slug>
    if status in (301, 302, 303, 307, 308):
        location = ""
        if hasattr(response, "headers"):
            location = response.headers.get("location", "")
        if not location and hasattr(response, "redirect"):
            location = str(response.redirect or "")
        if location and location.startswith("/") and re.match(r"^/\d", location):
            detail_html = await fetch_detail_page(
                urljoin(_ORIGIN, location), fetch_fn=fetch_fn
            )
            # Extract the tax code from the redirect path so the parser can
            # populate tax_code before any detail resolution or filtering.
            mst_match = re.search(r"^/(\d+)", location)
            tax_code = mst_match.group(1) if mst_match else ""
            return (
                f"<div class='search-results'><h3><a href='{location}'>{query}</a></h3>"
                f"<p>Mã số thuế: {tax_code}</p></div>{detail_html}",
                200,
            )
        raise MasothueAccessBlockedError(
            f"{url} redirected unexpectedly to {location}"
        )

    _status_for_url(status, url)
    if status != 200:
        raise MasothueAccessBlockedError(f"{url} returned {status}")

    html = _text(response)
    if not html or _looks_like_cloudflare(html):
        raise MasothueAccessBlockedError(f"{url} returned a cloudflare challenge")
    return html, status


async def fetch_detail_page(
    url: str,
    *,
    fetch_fn: Any | None = None,
) -> str:
    """Fetch a masothue.com detail page and return its HTML."""
    fetch = fetch_fn or AsyncFetcher.get

    try:
        response = await fetch(
            url,
            headers=_headers(),
            proxy=get_proxy_url(),
            stealthy_headers=True,
            timeout=getattr(config, "MASOTHUE_TIMEOUT_S", 30.0),
        )
    except TimeoutError as exc:
        raise MasothueTimeoutError(f"timeout for {url}") from exc
    except Exception as exc:
        raise MasothueAccessBlockedError(f"{url} fetch failed: {exc}") from exc

    status = getattr(response, "status", 0)
    _status_for_url(status, url)
    if status != 200:
        raise MasothueAccessBlockedError(f"{url} returned {status}")

    html = _text(response)
    if not html or _looks_like_cloudflare(html):
        raise MasothueAccessBlockedError(f"{url} returned a cloudflare challenge")
    return html


async def fetch_ajax_token(
    *,
    fetch_fn: Any | None = None,
) -> str | None:
    """POST to /Ajax/Token and return the token value if successful.

    V1 uses the GET HTML flow as primary; this is a fallback.
    """
    fetch = fetch_fn or AsyncFetcher.post
    url = f"{_ORIGIN}/Ajax/Token"
    r = random.randint(1_000_000, 9_999_999)

    try:
        response = await fetch(
            url,
            data={"r": r},
            headers={
                **_headers(),
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
            proxy=get_proxy_url(),
            stealthy_headers=True,
            timeout=getattr(config, "MASOTHUE_TIMEOUT_S", 30.0),
        )
    except Exception as exc:
        logger.debug("masothue AJAX token fetch failed: %s", exc)
        return None

    status = getattr(response, "status", 0)
    if status != 200:
        return None
    try:
        import json

        payload = json.loads(_text(response))
        return payload.get("token")
    except Exception:
        return None


async def fetch_ajax_search(
    query: str,
    search_type: str,
    *,
    fetch_fn: Any | None = None,
) -> dict[str, Any]:
    """POST to /Ajax/Search and return the raw JSON envelope."""
    token = await fetch_ajax_token(fetch_fn=fetch_fn)
    if not token:
        raise MasothueDecodeError("could not obtain AJAX token")

    fetch = fetch_fn or AsyncFetcher.post
    url = f"{_ORIGIN}/Ajax/Search"
    try:
        response = await fetch(
            url,
            data={
                "q": query,
                "type": search_type,
                "token": token,
                "force-search": 1,
            },
            headers={
                **_headers(),
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
            proxy=get_proxy_url(),
            stealthy_headers=True,
            timeout=getattr(config, "MASOTHUE_TIMEOUT_S", 30.0),
        )
    except Exception as exc:
        raise MasothueAccessBlockedError(f"{url} fetch failed: {exc}") from exc

    status = getattr(response, "status", 0)
    _status_for_url(status, url)
    if status != 200:
        raise MasothueAccessBlockedError(f"{url} returned {status}")

    try:
        import json

        return json.loads(_text(response))
    except Exception as exc:
        raise MasothueDecodeError(f"could not decode AJAX search: {exc}") from exc


def _page_delay() -> float:
    return max(0.0, getattr(config, "MASOTHUE_PAGE_DELAY_S", 1.0))


async def fetch_all_pages(
    query: str,
    search_type: str = "auto",
    max_pages: int = 5,
    *,
    fetch_fn: Any | None = None,
) -> list[str]:
    """Fetch up to ``max_pages`` search pages, pacing between requests."""
    pages: list[str] = []
    for page in range(1, max_pages + 1):
        html, _ = await fetch_search_page(
            query, search_type, page, fetch_fn=fetch_fn
        )
        pages.append(html)
        if page < max_pages:
            await asyncio.sleep(_page_delay())
    return pages

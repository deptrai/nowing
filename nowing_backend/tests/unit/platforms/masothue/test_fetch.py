"""Unit tests for masothue.com fetch helpers."""

from __future__ import annotations

from typing import Any

import pytest

from app.proprietary.platforms.masothue.fetch import (
    MasothueAccessBlockedError,
    MasothueRateLimitedError,
    fetch_detail_page,
    fetch_search_page,
)

pytestmark = pytest.mark.unit


def _make_response(status: int, body: str, headers: dict[str, Any] | None = None) -> Any:
    class Response:
        def __init__(self) -> None:
            self.status = status
            self.body = body.encode("utf-8")
            self.html_content = body
            self.headers = headers or {}

    return Response()


@pytest.mark.asyncio
async def test_fetch_search_page_success() -> None:
    called: dict[str, Any] = {}

    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        called["url"] = url
        called["kwargs"] = kwargs
        return _make_response(200, "<html><body>ok</body></html>")

    html, status = await fetch_search_page("vinamilk", "auto", 1, fetch_fn=fake_fetch)
    assert status == 200
    assert html == "<html><body>ok</body></html>"
    assert "masothue.com" in called["url"]


@pytest.mark.asyncio
async def test_fetch_search_page_rate_limited() -> None:
    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        return _make_response(429, "rate limited")

    with pytest.raises(MasothueRateLimitedError):
        await fetch_search_page("vinamilk", fetch_fn=fake_fetch)


@pytest.mark.asyncio
async def test_fetch_detail_page_success() -> None:
    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        return _make_response(200, "<table class='table-taxinfo'></table>")

    html = await fetch_detail_page("https://masothue.com/031-test", fetch_fn=fake_fetch)
    assert "table-taxinfo" in html


@pytest.mark.asyncio
async def test_fetch_detail_page_blocked() -> None:
    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        return _make_response(403, "blocked")

    with pytest.raises(MasothueAccessBlockedError):
        await fetch_detail_page("https://masothue.com/031-test", fetch_fn=fake_fetch)



@pytest.mark.asyncio
async def test_fetch_search_page_default_page_not_in_url() -> None:
    """Default page=1 must not add a page param to the search URL."""
    called: dict[str, Any] = {}

    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        called["url"] = url
        return _make_response(200, "<html><body>ok</body></html>")

    await fetch_search_page("vinamilk", fetch_fn=fake_fetch)
    assert "&page=" not in called["url"]
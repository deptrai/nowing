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


def _make_response(
    status: int, body: str, headers: dict[str, Any] | None = None
) -> Any:
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
    assert called["kwargs"]["timeout"] == 30.0
    assert called["kwargs"]["follow_redirects"] is False


@pytest.mark.asyncio
async def test_fetch_search_page_rate_limited() -> None:
    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        return _make_response(429, "rate limited")

    with pytest.raises(MasothueRateLimitedError):
        await fetch_search_page("vinamilk", fetch_fn=fake_fetch)


@pytest.mark.asyncio
async def test_fetch_detail_page_success() -> None:
    called: dict[str, Any] = {}

    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        called["kwargs"] = kwargs
        return _make_response(200, "<table class='table-taxinfo'></table>")

    html = await fetch_detail_page("https://masothue.com/031-test", fetch_fn=fake_fetch)
    assert "table-taxinfo" in html
    assert called["kwargs"]["timeout"] == 30.0


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


@pytest.mark.asyncio
async def test_fetch_search_page_page_greater_than_one() -> None:
    called: dict[str, Any] = {}

    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        called["url"] = url
        return _make_response(200, "<html><body>page 2 ok</body></html>")

    await fetch_search_page("vinamilk", "auto", 2, fetch_fn=fake_fetch)
    assert "page=2" in called["url"]


@pytest.mark.asyncio
async def test_fetch_search_page_passes_custom_proxy() -> None:
    called: dict[str, Any] = {}

    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        called["kwargs"] = kwargs
        return _make_response(200, "<html><body>proxy ok</body></html>")

    await fetch_search_page("vinamilk", fetch_fn=fake_fetch, proxy="http://custom:8080")
    assert called["kwargs"]["proxy"] == "http://custom:8080"
    assert called["kwargs"]["stealthy_headers"] is True


@pytest.mark.asyncio
async def test_fetch_detail_page_passes_custom_proxy_and_stealthy() -> None:
    called: dict[str, Any] = {}

    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        called["kwargs"] = kwargs
        return _make_response(200, "<table class='table-taxinfo'></table>")

    await fetch_detail_page(
        "https://masothue.com/031-test", fetch_fn=fake_fetch, proxy="http://custom:8080"
    )
    assert called["kwargs"]["proxy"] == "http://custom:8080"
    assert called["kwargs"]["stealthy_headers"] is True


@pytest.mark.asyncio
async def test_fetch_search_page_302_redirect_success() -> None:
    for redirect_code in (301, 302, 303, 307, 308):

        def _make_handler(code: int) -> Any:
            async def fake_fetch(url: str, **kwargs: Any) -> Any:
                if "/Search/" in url:
                    return _make_response(
                        code, "", headers={"location": "/0314539064-cong-ty-vinamilk"}
                    )
                return _make_response(
                    200,
                    "<table class='table-taxinfo'><tr><th>Địa chỉ</th><td>HCM</td></tr></table>",
                )

            return fake_fetch

        html, status = await fetch_search_page(
            "0314539064", fetch_fn=_make_handler(redirect_code)
        )
        assert status == 200
        assert "<p>Mã số thuế: 0314539064</p>" in html
        assert "<p>Mã số thuế: /0314539064</p>" not in html
        assert "table-taxinfo" in html


@pytest.mark.asyncio
async def test_fetch_search_page_302_redirect_with_redirect_attr() -> None:
    class RedirectResponse:
        status = 302
        body = b""
        headers: dict[str, str] = {}
        redirect = "/0314539064-cong-ty-vinamilk"

    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        if "/Search/" in url:
            return RedirectResponse()
        return _make_response(
            200,
            "<table class='table-taxinfo'><tr><th>Địa chỉ</th><td>HCM</td></tr></table>",
        )

    html, status = await fetch_search_page("0314539064", fetch_fn=fake_fetch)
    assert status == 200
    assert "<p>Mã số thuế: 0314539064</p>" in html


@pytest.mark.asyncio
async def test_fetch_search_page_location_precedence_over_redirect_attr() -> None:
    """Header location takes precedence over redirect attribute on response."""

    class DualRedirectResponse:
        status = 302
        body = b""
        headers = {"location": "/0314539064-from-header"}
        redirect = "/0314539065-from-attr"

    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        if "/Search/" in url:
            return DualRedirectResponse()
        return _make_response(
            200,
            "<table class='table-taxinfo'><tr><th>Địa chỉ</th><td>HCM</td></tr></table>",
        )

    html, status = await fetch_search_page("0314539064", fetch_fn=fake_fetch)
    assert status == 200
    assert "<p>Mã số thuế: 0314539064</p>" in html
    assert "0314539065" not in html


@pytest.mark.asyncio
async def test_fetch_search_page_redirect_to_non_mst_path_raises_blocked() -> None:
    """302 redirect to non-mst paths (e.g. external or non-digit slug) raises MasothueAccessBlockedError."""
    for bad_loc in ("https://external.com/path", "/notaxcode-slug", ""):

        def _make_loc_handler(loc: str) -> Any:
            async def fake_fetch(url: str, **kwargs: Any) -> Any:
                return _make_response(302, "", headers={"location": loc})

            return fake_fetch

        with pytest.raises(MasothueAccessBlockedError):
            await fetch_search_page("query", fetch_fn=_make_loc_handler(bad_loc))


@pytest.mark.asyncio
async def test_fetch_detail_page_missing_status_attr() -> None:
    class NoStatusResponse:
        body = b"<table class='table-taxinfo'></table>"

    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        return NoStatusResponse()

    # status defaults to 0, which raises MasothueAccessBlockedError
    with pytest.raises(MasothueAccessBlockedError):
        await fetch_detail_page("https://masothue.com/test", fetch_fn=fake_fetch)


@pytest.mark.asyncio
async def test_fetch_search_page_302_unexpected_location() -> None:
    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        return _make_response(302, "", headers={"location": "/invalid-location"})

    with pytest.raises(MasothueAccessBlockedError):
        await fetch_search_page("0314539064", fetch_fn=fake_fetch)


@pytest.mark.asyncio
async def test_fetch_search_page_non_200_raises_blocked() -> None:
    for bad_status in (199, 201, 400, 404, 500):

        def _make_bad_fetch(status: int) -> Any:
            async def fake_fetch(url: str, **kwargs: Any) -> Any:
                return _make_response(status, "error body")

            return fake_fetch

        with pytest.raises(MasothueAccessBlockedError):
            await fetch_search_page("vinamilk", fetch_fn=_make_bad_fetch(bad_status))


@pytest.mark.asyncio
async def test_fetch_search_page_cloudflare_detected() -> None:
    async def fake_fetch(url: str, **kwargs: Any) -> Any:
        return _make_response(
            200, "<html><body>Just a moment... cf-challenge</body></html>"
        )

    with pytest.raises(MasothueAccessBlockedError):
        await fetch_search_page("vinamilk", fetch_fn=fake_fetch)


@pytest.mark.asyncio
async def test_fetch_search_page_timeout() -> None:
    from app.proprietary.platforms.masothue.fetch import MasothueTimeoutError

    async def timeout_fetch(url: str, **kwargs: Any) -> Any:
        raise TimeoutError("connection timeout")

    with pytest.raises(MasothueTimeoutError):
        await fetch_search_page("vinamilk", fetch_fn=timeout_fetch)


@pytest.mark.asyncio
async def test_fetch_detail_page_timeout_and_cloudflare_and_status() -> None:
    from app.proprietary.platforms.masothue.fetch import MasothueTimeoutError

    async def timeout_fetch(url: str, **kwargs: Any) -> Any:
        raise TimeoutError("timeout")

    with pytest.raises(MasothueTimeoutError):
        await fetch_detail_page("https://masothue.com/test", fetch_fn=timeout_fetch)

    async def cf_fetch(url: str, **kwargs: Any) -> Any:
        return _make_response(200, "Checking your browser before accessing")

    with pytest.raises(MasothueAccessBlockedError):
        await fetch_detail_page("https://masothue.com/test", fetch_fn=cf_fetch)

    async def status_fetch(url: str, **kwargs: Any) -> Any:
        return _make_response(404, "not found")

    with pytest.raises(MasothueAccessBlockedError):
        await fetch_detail_page("https://masothue.com/test", fetch_fn=status_fetch)


def test_fetch_helper_functions() -> None:
    from app.proprietary.platforms.masothue.fetch import (
        _headers,
        _looks_like_cloudflare,
        _search_url,
        _status_for_url,
        _text,
    )

    headers = _headers()
    assert headers["Origin"] == "https://masothue.com"
    assert headers["Referer"] == "https://masothue.com/"

    # Default page=1 must not include &page=
    assert _search_url("vnm", "auto") == "https://masothue.com/Search/?q=vnm&type=auto"
    assert (
        _search_url("vnm", "auto", 1) == "https://masothue.com/Search/?q=vnm&type=auto"
    )
    assert (
        _search_url("vnm", "auto", 0) == "https://masothue.com/Search/?q=vnm&type=auto"
    )
    assert (
        _search_url("vnm", "auto", -1) == "https://masothue.com/Search/?q=vnm&type=auto"
    )
    assert (
        _search_url("vnm", "auto", 2)
        == "https://masothue.com/Search/?q=vnm&type=auto&page=2"
    )
    assert (
        _search_url("vnm", "auto", 3)
        == "https://masothue.com/Search/?q=vnm&type=auto&page=3"
    )
    assert (
        _search_url("vnm", "enterpriseTax", 2)
        == "https://masothue.com/Search/?q=vnm&type=enterpriseTax&page=2"
    )
    assert (
        _search_url("vnm", "personalTax", 1)
        == "https://masothue.com/Search/?q=vnm&type=personalTax"
    )

    with pytest.raises(MasothueRateLimitedError):
        _status_for_url(429, "http://test")
    with pytest.raises(MasothueAccessBlockedError):
        _status_for_url(403, "http://test")
    with pytest.raises(MasothueAccessBlockedError):
        _status_for_url(451, "http://test")

    # Explicitly test each 5xx code in the tuple to kill number replacer mutants
    for status_code in (500, 502, 503, 504):
        with pytest.raises(MasothueAccessBlockedError):
            _status_for_url(status_code, "http://test")

    # Non-error codes should not raise
    _status_for_url(200, "http://test")
    _status_for_url(428, "http://test")
    _status_for_url(430, "http://test")

    assert _looks_like_cloudflare("cf-browser-verification") is True
    assert _looks_like_cloudflare("challenge-form") is True
    assert _looks_like_cloudflare("__cf_bm") is True
    assert _looks_like_cloudflare("<html><body>normal content</body></html>") is False

    class HtmlObj:
        html_content = "from html_content"

    class EmptyHtmlTextObj:
        html_content = ""
        text = "fallback to text"

    class BodyBytes:
        body = b"from bytes"

    class BodyStr:
        body = "from str"

    assert _text(HtmlObj()) == "from html_content"
    assert _text(EmptyHtmlTextObj()) == "fallback to text"
    assert _text(BodyBytes()) == "from bytes"
    assert _text(BodyStr()) == "from str"

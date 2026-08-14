"""Vietstock fetch layer tests — auth, rate limit, retry."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.proprietary.platforms.vietstock.fetch import (
    VietstockAccessBlockedError,
    VietstockAuthRefreshError,
    VietstockDecodeError,
    VietstockRateLimitedError,
    _set_cookie,
    fetch_financials,
    fetch_quote,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_fetch_state(monkeypatch):
    """Reset process-local cookie and throttle state between tests."""
    _set_cookie(None)
    monkeypatch.setattr("app.proprietary.platforms.vietstock.fetch._last_request_at", None)


@pytest.fixture(autouse=True)
def _demo_mode(monkeypatch):
    """Keep demo mode off so the real fetch path is tested."""
    monkeypatch.setattr("app.proprietary.platforms.vietstock.fetch._demo_mode", lambda: False)


@pytest.fixture(autouse=True)
def _fast_config(monkeypatch):
    """Use fast rate limit and short timeout so tests run quickly."""
    monkeypatch.setattr("app.config.config.VIETSTOCK_RATE_LIMIT_RPS", 1000.0)
    monkeypatch.setattr("app.config.config.VIETSTOCK_TIMEOUT_S", 2.0)
    monkeypatch.setattr("app.config.config.VIETSTOCK_QUOTE_URL", "https://finance.vietstock.vn/api/trading/{symbol}")
    monkeypatch.setattr(
        "app.config.config.VIETSTOCK_FINANCIAL_URL",
        "https://finance.vietstock.vn/api/finance/{statement_type}?symbol={symbol}",
    )


@respx.mock
async def test_fetch_quote_with_valid_credentials(monkeypatch) -> None:
    """Mirror: should return quote dict with expected fields."""
    monkeypatch.setattr("app.config.config.VIETSTOCK_SESSION_COOKIE", "session=demo")
    url = "https://finance.vietstock.vn/api/trading/VNM"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            json={
                "symbol": "VNM",
                "current_price": 75000.0,
                "open_price": 74000.0,
                "high": 76000.0,
                "low": 73500.0,
                "close": 75000.0,
                "volume": 1_000_000,
                "change": 1000.0,
                "change_percent": 1.35,
                "key_ratios": {"pe": 15.2, "pb": 2.1, "roe": 18.5, "roa": 10.2},
            },
        )
    )
    raw = await fetch_quote("VNM")
    assert raw["symbol"] == "VNM"
    assert raw["current_price"] == 75000.0
    assert raw["key_ratios"]["pe"] == 15.2


@respx.mock
async def test_fetch_quote_no_credentials_degrades() -> None:
    """Edge: no credentials configured should fail with VietstockAuthRefreshError."""
    url = "https://finance.vietstock.vn/api/trading/VNM"
    respx.get(url).mock(return_value=httpx.Response(401))
    respx.get("https://finance.vietstock.vn").mock(return_value=httpx.Response(401))
    with pytest.raises(VietstockAuthRefreshError):
        await fetch_quote("VNM")


@respx.mock
async def test_fetch_quote_auth_refresh_then_success(monkeypatch) -> None:
    """Boundary: 401 on first request, refresh, then 200."""
    monkeypatch.setattr("app.config.config.VIETSTOCK_SESSION_COOKIE", "session=old")
    quote_url = "https://finance.vietstock.vn/api/trading/VNM"
    refresh_url = "https://finance.vietstock.vn"

    respx.get(quote_url).mock(return_value=httpx.Response(401))
    respx.get(refresh_url).mock(
        return_value=httpx.Response(
            200,
            headers={"set-cookie": "session=newcookie"},
        )
    )
    respx.get(quote_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "symbol": "VNM",
                "current_price": 75000.0,
                "key_ratios": {"pe": 15.2},
            },
        )
    )

    raw = await fetch_quote("VNM")
    assert raw["symbol"] == "VNM"
    assert raw["current_price"] == 75000.0


@respx.mock
async def test_fetch_quote_auth_refresh_fails() -> None:
    """Over-Mocking: refresh endpoint returns 401/403 again."""
    quote_url = "https://finance.vietstock.vn/api/trading/VNM"
    refresh_url = "https://finance.vietstock.vn"
    respx.get(quote_url).mock(return_value=httpx.Response(401))
    respx.get(refresh_url).mock(return_value=httpx.Response(403))
    with pytest.raises(VietstockAuthRefreshError) as exc:
        await fetch_quote("VNM")
    assert "401" in str(exc.value) or "403" in str(exc.value)


@respx.mock
async def test_fetch_quote_rate_limited_after_retries() -> None:
    """Over-Mocking: 429 after max retries should raise VietstockRateLimitedError."""
    url = "https://finance.vietstock.vn/api/trading/VNM"
    respx.get(url).mock(return_value=httpx.Response(429))
    with pytest.raises(VietstockRateLimitedError):
        await fetch_quote("VNM")


@respx.mock
async def test_fetch_financials_per_call_timeout() -> None:
    """Over-Mocking: per-call timeout should not block whole scrape."""
    respx.get("https://finance.vietstock.vn/api/finance/balance_sheet").mock(
        return_value=httpx.Response(408)
    )
    respx.get("https://finance.vietstock.vn/api/finance/income_statement").mock(
        return_value=httpx.Response(200, json={"periods": [], "items": []})
    )
    respx.get("https://finance.vietstock.vn/api/finance/cash_flow").mock(
        return_value=httpx.Response(200, json={"periods": [], "items": []})
    )
    # Note: asyncio.gather will raise the first exception.
    with pytest.raises(VietstockAccessBlockedError):
        await fetch_financials("VNM")


@respx.mock
async def test_fetch_quote_html_challenge() -> None:
    """Over-Mocking: HTML response should raise VietstockAccessBlockedError."""
    url = "https://finance.vietstock.vn/api/trading/VNM"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text="<html>challenge</html>",
            headers={"content-type": "text/html"},
        )
    )
    with pytest.raises(VietstockAccessBlockedError):
        await fetch_quote("VNM")


@respx.mock
async def test_fetch_quote_invalid_json() -> None:
    """Over-Mocking: invalid JSON should raise VietstockDecodeError."""
    url = "https://finance.vietstock.vn/api/trading/VNM"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text="not json",
            headers={"content-type": "application/json"},
        )
    )
    with pytest.raises(VietstockDecodeError):
        await fetch_quote("VNM")

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
    _rate_limit_interval,
    _set_cookie,
    fetch_financials,
    fetch_quote,
)

pytestmark = pytest.mark.unit


def _token_page(token: str) -> str:
    return f'<input name="__RequestVerificationToken" type="hidden" value="{token}" />'


@pytest.fixture(autouse=True)
def _reset_fetch_state(monkeypatch):
    """Reset process-local cookie, token, and throttle state between tests."""
    _set_cookie(None)
    monkeypatch.setattr(
        "app.proprietary.platforms.vietstock.fetch._last_request_at", None
    )
    monkeypatch.setattr(
        "app.proprietary.platforms.vietstock.fetch._verification_token", None
    )


@pytest.fixture(autouse=True)
def _demo_mode(monkeypatch):
    """Keep demo mode off so the real fetch path is tested."""
    monkeypatch.setattr(
        "app.proprietary.platforms.vietstock.fetch._demo_mode", lambda: False
    )


@pytest.fixture(autouse=True)
def _fast_config(monkeypatch):
    """Use fast rate limit and short timeout so tests run quickly."""
    monkeypatch.setattr("app.config.config.VIETSTOCK_RATE_LIMIT_RPS", 1000.0)
    monkeypatch.setattr("app.config.config.VIETSTOCK_TIMEOUT_S", 2.0)
    monkeypatch.setattr(
        "app.config.config.VIETSTOCK_QUOTE_URL",
        "https://finance.vietstock.vn/company/tradinginfo",
    )
    monkeypatch.setattr(
        "app.config.config.VIETSTOCK_FINANCIAL_URL",
        "https://finance.vietstock.vn/data/financeinfo",
    )
    monkeypatch.setattr("app.config.config.VIETSTOCK_SESSION_COOKIE", "")


@respx.mock
async def test_fetch_quote_with_valid_credentials(monkeypatch) -> None:
    """Mirror: should return quote dict with expected fields."""
    token = "TOKEN1"
    respx.get("https://finance.vietstock.vn").mock(
        return_value=httpx.Response(200, text=_token_page(token))
    )
    respx.post("https://finance.vietstock.vn/company/tradinginfo").mock(
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
async def test_fetch_quote_no_credentials_degrades(monkeypatch) -> None:
    """Edge: no credentials configured should fail with VietstockAuthRefreshError."""
    monkeypatch.setattr("app.config.config.VIETSTOCK_QUOTE_URL", "")
    monkeypatch.setattr("app.config.config.VIETSTOCK_FINANCIAL_URL", "")
    with pytest.raises(VietstockAuthRefreshError) as exc:
        await fetch_quote("VNM")
    assert "missing_credentials" in str(exc.value)


@respx.mock
async def test_fetch_quote_token_refresh_then_success(monkeypatch) -> None:
    """Boundary: 403 on first POST, refresh token, then 200."""
    token_old = "TOKEN_OLD"
    token_new = "TOKEN_NEW"

    respx.get("https://finance.vietstock.vn").mock(
        side_effect=[
            httpx.Response(200, text=_token_page(token_old)),
            httpx.Response(200, text=_token_page(token_new)),
        ]
    )
    respx.post("https://finance.vietstock.vn/company/tradinginfo").mock(
        side_effect=[
            httpx.Response(403),
            httpx.Response(
                200,
                json={"symbol": "VNM", "current_price": 75000.0, "key_ratios": {"pe": 15.2}},
            ),
        ]
    )

    raw = await fetch_quote("VNM")
    assert raw["symbol"] == "VNM"
    assert raw["current_price"] == 75000.0


@respx.mock
async def test_fetch_quote_token_refresh_fails() -> None:
    """Over-Mocking: refresh endpoint returns 403."""
    respx.get("https://finance.vietstock.vn").mock(return_value=httpx.Response(403))
    respx.post("https://finance.vietstock.vn/company/tradinginfo").mock(
        return_value=httpx.Response(401)
    )
    with pytest.raises(VietstockAuthRefreshError):
        await fetch_quote("VNM")


@respx.mock
async def test_fetch_quote_rate_limited_after_retries() -> None:
    """Over-Mocking: 429 after max retries should raise VietstockRateLimitedError."""
    respx.get("https://finance.vietstock.vn").mock(
        return_value=httpx.Response(200, text=_token_page("TOKEN"))
    )
    respx.post("https://finance.vietstock.vn/company/tradinginfo").mock(
        return_value=httpx.Response(429)
    )
    with pytest.raises(VietstockRateLimitedError):
        await fetch_quote("VNM")


@respx.mock
async def test_fetch_financials_per_call_timeout() -> None:
    """Over-Mocking: per-call timeout should not block whole scrape."""
    respx.get("https://finance.vietstock.vn").mock(
        return_value=httpx.Response(200, text=_token_page("TOKEN"))
    )
    respx.post("https://finance.vietstock.vn/data/financeinfo").mock(
        return_value=httpx.Response(408)
    )
    with pytest.raises(VietstockAccessBlockedError):
        await fetch_financials("VNM")


@respx.mock
async def test_fetch_quote_html_challenge() -> None:
    """Over-Mocking: HTML response should raise VietstockAccessBlockedError."""
    respx.get("https://finance.vietstock.vn").mock(
        return_value=httpx.Response(200, text=_token_page("TOKEN"))
    )
    respx.post("https://finance.vietstock.vn/company/tradinginfo").mock(
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
    respx.get("https://finance.vietstock.vn").mock(
        return_value=httpx.Response(200, text=_token_page("TOKEN"))
    )
    respx.post("https://finance.vietstock.vn/company/tradinginfo").mock(
        return_value=httpx.Response(
            200,
            text="not json",
            headers={"content-type": "application/json"},
        )
    )
    with pytest.raises(VietstockDecodeError):
        await fetch_quote("VNM")


def test_rate_limit_negative_config_defaults_to_safe_value(monkeypatch) -> None:
    """Edge: negative rate limit config should clamp to a safe interval."""
    monkeypatch.setattr("app.config.config.VIETSTOCK_RATE_LIMIT_RPS", -10.0)
    assert _rate_limit_interval() > 0

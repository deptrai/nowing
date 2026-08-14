"""Vietstock fetch layer tests — auth, rate limit, retry."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def _demo_credentials():
    return {
        "cookies": {"session_id": "demo"},
        "token": "",
    }


async def test_fetch_quote_with_valid_credentials() -> None:
    """Mirror: should return quote dict with expected fields."""
    # TODO: mock httpx response
    raise NotImplementedError("red phase — implement fake http client")


async def test_fetch_quote_no_credentials_degrades() -> None:
    """Edge: no credentials configured should degrade without network."""
    # TODO: configure no credentials
    raise NotImplementedError("red phase — implement credential lookup")


async def test_fetch_quote_auth_refresh_then_success() -> None:
    """Boundary: 401 on first request, refresh, then 200."""
    # TODO: mock 401 then 200
    raise NotImplementedError("red phase — implement mock refresh")


async def test_fetch_quote_auth_refresh_fails() -> None:
    """Over-Mocking: refresh endpoint returns 401/403 again."""
    # TODO: mock refresh failure
    raise NotImplementedError("red phase — implement mock refresh failure")


async def test_fetch_quote_rate_limited_after_retries() -> None:
    """Over-Mocking: 429 after max retries should raise VietstockRateLimitedError."""
    # TODO: mock repeated 429
    raise NotImplementedError("red phase — implement 429 mock")


async def test_fetch_financials_per_call_timeout() -> None:
    """Over-Mocking: per-call timeout should not block whole scrape."""
    # TODO: mock timeout
    raise NotImplementedError("red phase — implement timeout mock")


async def test_fetch_quote_html_challenge() -> None:
    """Over-Mocking: HTML response should raise VietstockAccessBlockedError."""
    # TODO: mock HTML response
    raise NotImplementedError("red phase — implement HTML challenge mock")

"""CafeF rate-limiting integration tests."""

from __future__ import annotations

import time

from app.config import config
from app.proprietary.platforms.cafef import fetch
from app.proprietary.platforms.cafef.fetch import fetch_quote


def _quote_response() -> dict:
    return {"symbol": "VCB", "price": 80.0}


async def test_throttle_enforces_interval(monkeypatch, http_mock) -> None:
    """Two rapid calls must wait at least 1/rps seconds between starts."""
    monkeypatch.setattr(config, "CAFEF_DEMO_MODE", False)
    monkeypatch.setattr(config, "CAFEF_RATE_LIMIT_RPS", 2.0)
    monkeypatch.setattr(config, "CAFEF_TIMEOUT_S", 5.0)
    monkeypatch.setattr(config, "CAFEF_QUOTE_URL", "https://apiweb.cafef.vn/api/v1/Stock/Quote?symbol={symbol}")
    monkeypatch.setattr(fetch, "_last_request_at", None)

    http_mock(
        {
            (
                "https://apiweb.cafef.vn/api/v1/Stock/Quote",
                (("symbol", "VCB"),),
            ): (200, _quote_response()),
        }
    )

    t0 = time.perf_counter()
    await fetch_quote("VCB")
    await fetch_quote("VCB")
    elapsed = time.perf_counter() - t0

    # interval = 1 / 2.0 = 0.5 s; allow some slack for the fake client.
    assert elapsed >= 0.45

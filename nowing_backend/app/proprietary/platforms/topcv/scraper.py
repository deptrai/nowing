"""TopCV HTML fetcher with anti-bot handling."""

from __future__ import annotations

from typing import Any


async def scrape_topcv(params: dict[str, Any]) -> dict[str, Any]:
    """Skeleton: fetch TopCV search pages via AD-19 web crawler stack.

    Hard gate: TopCV anti-bot POC and ToS review must pass before this is
    implemented. Cost is metered through WEB_CRAWL + captcha solves.
    """
    return {
        "items": [],
        "cost_micros": 0,
        "degraded": True,
        "degradation_reason": "anti_bot_poc_pending",
    }

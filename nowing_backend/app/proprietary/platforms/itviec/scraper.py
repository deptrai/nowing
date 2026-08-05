"""ITviec server-rendered HTML parser."""

from __future__ import annotations

from typing import Any


async def scrape_itviec(params: dict[str, Any]) -> dict[str, Any]:
    """Skeleton: parse `GET https://itviec.com/it-jobs/{keyword}`.

    Hard gate: ToS review for ITviec must pass before this is implemented.
    """
    return {
        "items": [],
        "cost_micros": 0,
        "degraded": True,
        "degradation_reason": "tos_review_pending",
    }

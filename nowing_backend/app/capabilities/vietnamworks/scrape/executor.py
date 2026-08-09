"""``vietnamworks.scrape`` executor: verb input → API fetcher → job listings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Optional

import httpx

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.proprietary.platforms.vietnamworks import scrape_vietnamworks

from .schemas import ScrapeInput, ScrapeOutput

ScrapeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


# Degradation reasons that benefit from human review / rate-limit handling.
_REVIEW_REASONS = {
    "rate_limited",
    "access_blocked",
}


def _next_action(degradation_reason: str | None) -> str | None:
    if degradation_reason == "rate_limited":
        return "Retry after reducing request rate or rotating egress."
    if degradation_reason == "access_blocked":
        return "Access blocked by VietnamWorks; escalate to human review."
    return None


def build_scrape_executor(scrape_fn: Optional[ScrapeFn] = None) -> Executor:  # noqa: UP045
    """Return an executor that calls the VietnamWorks proprietary fetcher."""

    _scrape = scrape_fn or scrape_vietnamworks

    async def execute(
        input: ScrapeInput, ctx: CapabilityContext | None = None
    ) -> ScrapeOutput:
        emit_progress("fetching", "VietnamWorks job search")

        params = input.model_dump(exclude_none=True)

        items: list[dict[str, Any]] = []

        try:
            for page in range(1, input.max_pages + 1):
                remaining = input.max_items - len(items)
                if remaining <= 0:
                    break

                hits_per_page = min(remaining, config.VIETNAMWORKS_MAX_ITEMS)
                page_params = {
                    **params,
                    "page": page,
                    "max_pages": 1,
                    "max_items": remaining,
                    "hitsPerPage": hits_per_page,
                }
                raw = await _scrape(page_params)

                if raw.get("degraded"):
                    return ScrapeOutput(
                        items=items,
                        cost_micros=0,
                        degraded=True,
                        degradation_reason=raw.get("degradation_reason"),
                        next_action=_next_action(raw.get("degradation_reason")),
                    )

                page_items = raw.get("items", [])
                if not page_items:
                    break

                items.extend(page_items)
                if len(items) >= input.max_items:
                    break

                # If the scraper already reached the end of the result set, stop early.
                if raw.get("meta", {}).get("nbPages") is not None and page >= int(
                    raw["meta"]["nbPages"]
                ):
                    break

        except httpx.TimeoutException:
            return ScrapeOutput(
                items=items,
                cost_micros=0,
                degraded=True,
                degradation_reason="timeout",
                next_action=_next_action("timeout"),
            )
        except Exception:
            return ScrapeOutput(
                items=items,
                cost_micros=0,
                degraded=True,
                degradation_reason="api_error",
                next_action=_next_action("api_error"),
            )

        items = items[: input.max_items]
        cost_micros = len(items) * config.VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM
        emit_progress(
            "done",
            "VietnamWorks job search complete",
            current=len(items),
            total=input.max_items,
            unit="item",
        )
        return ScrapeOutput(
            items=items,
            cost_micros=cost_micros,
            degraded=False,
            degradation_reason=None,
            next_action=None,
        )

    return execute

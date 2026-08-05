"""``vietnamworks.scrape`` executor: verb input → API fetcher → job listings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Optional

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.config import config
from app.proprietary.platforms.vietnamworks import scrape_vietnamworks

from .schemas import ScrapeInput, ScrapeOutput

ScrapeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def build_scrape_executor(scrape_fn: Optional[ScrapeFn] = None) -> Executor:  # noqa: UP045
    """Return an executor that calls the VietnamWorks proprietary fetcher."""

    _scrape = scrape_fn or scrape_vietnamworks

    async def execute(input: ScrapeInput) -> ScrapeOutput:
        import httpx

        emit_progress("fetching", "VietnamWorks job search")

        params = input.model_dump(exclude_none=True)
        params["max_items"] = input.max_items
        params["hitsPerPage"] = min(input.max_items, config.VIETNAMWORKS_MAX_ITEMS)

        items: list[dict[str, Any]] = []

        try:
            for page in range(1, input.max_pages + 1):
                page_params = {**params, "page": page, "max_pages": 1}
                raw = await _scrape(page_params)

                if raw.get("degraded"):
                    return ScrapeOutput(
                        items=items,
                        cost_micros=0,
                        degraded=True,
                        degradation_reason=raw.get("degradation_reason"),
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
            )
        except RuntimeError as exc:
            if "429" in str(exc):
                return ScrapeOutput(
                    items=items,
                    cost_micros=0,
                    degraded=True,
                    degradation_reason="rate_limited",
                )
            return ScrapeOutput(
                items=items,
                cost_micros=0,
                degraded=True,
                degradation_reason="api_error",
            )

        items = items[: input.max_items]
        cost_micros = len(items) * config.VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM
        return ScrapeOutput(
            items=items,
            cost_micros=cost_micros,
            degraded=False,
            degradation_reason=None,
        )

    return execute

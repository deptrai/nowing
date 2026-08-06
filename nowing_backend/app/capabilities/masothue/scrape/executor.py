"""``masothue.scrape`` executor: verb input → scraper → typed output."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.canonical.services.canonical_persist_service import upsert_canonical_entity
from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.proprietary.platforms.masothue import (
    MasothueAccessBlockedError,
    MasothueDecodeError,
    MasothueRateLimitedError,
    MasothueTimeoutError,
    scrape_masothue,
)
from app.proprietary.platforms.masothue.schemas import (
    MasothueScrapeOutput,
    MasothueSearchInput,
)
from app.services.company_aggregator import fingerprint, search_text

from .schemas import ScrapeInput, ScrapeOutput

logger = logging.getLogger(__name__)

ScrapeFn = Callable[..., Awaitable[MasothueScrapeOutput | dict[str, Any]]]


def _unwrap_result(
    result: MasothueScrapeOutput | dict[str, Any] | None,
) -> dict[str, Any]:
    if result is None:
        return {
            "items": [],
            "total_items": 0,
            "degraded": True,
            "degradation_reason": "unknown",
        }
    if isinstance(result, MasothueScrapeOutput):
        return {
            "items": [item.to_output() for item in result.items],
            "total_items": result.total_items,
            "degraded": result.degraded,
            "degradation_reason": result.degradation_reason,
        }
    return result


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape = scrape_fn or scrape_masothue

    async def execute(
        payload: ScrapeInput,
        ctx: CapabilityContext | None = None,
    ) -> ScrapeOutput:
        actor_input = MasothueSearchInput(**payload.model_dump(exclude_unset=True))

        emit_progress(
            "starting",
            "Resolving masothue.com companies",
            total=payload.max_items,
            unit="company",
        )

        try:
            raw = await scrape(actor_input)
        except MasothueRateLimitedError:
            logger.exception("masothue.scrape rate limited")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="rate_limited",
            )
        except MasothueDecodeError:
            logger.exception("masothue.scrape decode error")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="decode_error",
            )
        except MasothueTimeoutError:
            logger.exception("masothue.scrape timeout")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="timeout",
            )
        except (MasothueAccessBlockedError, Exception) as exc:
            logger.exception("masothue.scrape actor failed: %s", exc)
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="api_error",
            )

        result = _unwrap_result(raw)

        item_dicts = result.get("items", []) or []
        total = len(item_dicts)
        degraded = bool(result.get("degraded", False))

        # Build typed items. Pydantic will coerce dicts into MasothueCompany.
        items: list[Any] = []
        for item in item_dicts:
            if isinstance(item, dict):
                items.append(item)
            else:
                items.append(item.to_output())

        rate = getattr(config, "MASOTHUE_SCRAPE_MICROS_PER_ITEM", 3000)
        cost = total * rate

        # Persist each company to the canonical entity store.
        if ctx is not None:
            for item in items:
                try:
                    fp = fingerprint(item)
                    text = search_text(item)
                    title = item.get("name") or ""
                    source_record_id = item.get("tax_code") or fp
                    await upsert_canonical_entity(
                        ctx.session,
                        workspace_id=ctx.workspace_id,
                        entity_type="company",
                        fingerprint=fp,
                        title=title,
                        data=item,
                        search_text=text,
                        source_name="masothue",
                        source_record_id=source_record_id,
                        source_snapshot=item,
                        source_url=item.get("detail_url"),
                        source_fingerprint=fp,
                    )
                except Exception:
                    logger.exception("masothue canonical upsert failed")

        emit_progress(
            "done",
            f"Scraped {total} company(ies)",
            current=total,
            total=payload.max_items,
            unit="company",
        )

        return ScrapeOutput(
            items=item_dicts,
            cost_micros=cost,
            degraded=degraded,
            degradation_reason=result.get("degradation_reason"),
        )

    return execute

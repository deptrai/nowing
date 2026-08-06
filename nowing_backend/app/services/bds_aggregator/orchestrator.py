"""Orchestrate fan-out to the three P0 BĐS scrapers and aggregate results."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import (
    create_persist_outbox,
    upsert_canonical_entity,
)
from app.canonical.services.canonical_pii import redact_source_snapshot
from app.canonical.tenant_context import set_canonical_workspace_id
from app.capabilities.core.store import get_capability
from app.config import config
from app.observability.metrics import (
    categorize_exception,
    record_canonical_persist_failure,
)

from .dedupe import deduplicate, search_text
from .normalize import normalize_listing, to_batdongsan_city_code
from .schemas import VnBdsAggregatedListing, VnBdsAggregateInput, VnBdsAggregateOutput
from .scoring import score_listing

logger = logging.getLogger(__name__)


def _source_breakdown(
    source: str,
    items: list[Any],
    cost_micros: int,
    degraded: bool,
    reason: str | None,
) -> dict[str, Any]:
    return {
        source: {
            "items": len(items),
            "cost_micros": cost_micros,
            "degraded": degraded,
            "degradation_reason": reason,
        }
    }


def _build_child_payload(
    source: str, payload: VnBdsAggregateInput
) -> tuple[dict[str, Any], str | None]:
    """Map the aggregate input to one source-specific scraper payload."""
    base: dict[str, Any] = {
        "listing_type": payload.listing_type,
        "max_items": payload.max_items_per_source,
        "max_pages": payload.max_pages,
        "min_price": payload.min_price,
        "max_price": payload.max_price,
        "min_area": payload.min_area,
        "max_area": payload.max_area,
    }

    if source == "batdongsan":
        city_code = to_batdongsan_city_code(payload.city)
        if city_code is None:
            return {}, f"unknown_city:{payload.city}"
        base.update(
            {
                "city": city_code,
                "district_id": payload.district_id,
                "resolve_phones": payload.resolve_phones,
            }
        )
        return base, None

    if source == "chotot_bds":
        base.update(
            {
                "city": payload.city,
                "property_type": payload.property_type,
                "district": payload.district,
                "district_id": payload.district_id,
            }
        )
        return base, None

    if source == "muaban_bds":
        base.update(
            {
                "city": payload.city,
                "property_type": payload.property_type,
                "district": payload.district,
            }
        )
        return base, None

    return {}, f"unknown_source:{source}"


def _child_cost(items: list[Any], source: str, child_output: Any) -> int:
    """Use the child's reported cost when available, otherwise estimate."""
    if isinstance(child_output, dict):
        child_cost = child_output.get("cost_micros")
    else:
        child_cost = getattr(child_output, "cost_micros", None)
    if isinstance(child_cost, int):
        return child_cost
    rate_key = {
        "batdongsan": "BATDONGSAN_SCRAPE_MICROS_PER_ITEM",
        "chotot_bds": "CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM",
        "muaban_bds": "MUABAN_BDS_SCRAPE_MICROS_PER_ITEM",
    }.get(source, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM")
    rate = int(getattr(config, rate_key, 3500))
    return len(items) * rate


def _child_result(
    child_output: Any,
) -> tuple[list[dict[str, Any]], int, bool, str | None]:
    """Extract (items, cost, degraded, reason) from a scraper output."""
    if isinstance(child_output, dict):
        items = child_output.get("items", []) or []
        cost = child_output.get("cost_micros", 0) or 0
        degraded = bool(child_output.get("degraded", False))
        reason = child_output.get("degradation_reason")
    else:
        items = getattr(child_output, "items", []) or []
        cost = getattr(child_output, "cost_micros", 0) or 0
        degraded = bool(getattr(child_output, "degraded", False))
        reason = getattr(child_output, "degradation_reason", None)
    return items, cost, degraded, reason


def _cap_items(
    listings: list[VnBdsAggregatedListing], max_items: int
) -> list[VnBdsAggregatedListing]:
    if max_items < 0:
        return listings
    return listings[:max_items]


def _filter_by_confidence(
    listings: list[VnBdsAggregatedListing], min_confidence: float
) -> list[VnBdsAggregatedListing]:
    if min_confidence <= 0.0:
        return listings
    return [
        listing for listing in listings if listing.confidence_score >= min_confidence
    ]


_BDS_ENTITY_TYPE = "bds_listing"


def _build_bds_data(listing: VnBdsAggregatedListing) -> dict[str, Any]:
    """Return a serializable copy of the listing, including excluded fields."""
    data = listing.model_dump()
    # source_prices are excluded from the API schema but kept for canonical
    # provenance and merge history.
    if listing.source_prices:
        data["source_prices"] = listing.source_prices
    return data


def _redact_bds_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Return a source snapshot with PII fields removed or masked."""
    # ponytail: source snapshots do not need matching keys, so we drop even
    # one-way digests here. Central redaction removes owner/seller phones and
    # any *phone* / *email* heuristic keys as a second guard.
    return redact_source_snapshot(_BDS_ENTITY_TYPE, data)


def _build_bds_canonical_data(
    listing: VnBdsAggregatedListing,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Build canonical data with one-way keys for matching but no raw PII."""
    canonical_data = dict(data)
    # source_prices are intentionally excluded from the API schema but are
    # safe and useful for canonical provenance/price-conflict history.
    if listing.source_prices:
        canonical_data["source_prices"] = listing.source_prices
    # phone_key and address_key are one-way normalized keys safe for matching.
    if listing.phone_key:
        canonical_data["phone_key"] = listing.phone_key
    if listing.address_key:
        canonical_data["address_key"] = listing.address_key
    canonical_data.pop("contact", None)
    return canonical_data


async def _persist_bds_listing(
    session: AsyncSession,
    workspace_id: int,
    listing: VnBdsAggregatedListing,
) -> None:
    """Upsert one BĐS listing and each contributing source into canonical storage."""
    data = _build_bds_data(listing)
    source_snapshot = _redact_bds_snapshot(data)
    canonical_data = _build_bds_canonical_data(listing, data)
    fingerprint = listing.canonical_id
    search_text_value = search_text(listing)
    conflict_flags = [flag.model_dump() for flag in listing.conflict_flags]

    # ponytail: day-one implementation links each source record separately.
    # Each call to upsert_canonical_entity is idempotent on the entity
    # fingerprint and on the (source_name, source_record_id) provenance key.
    for source in listing.sources:
        raw_source_id = listing.source_ids.get(source)
        source_record_id = str(raw_source_id if raw_source_id is not None else source)
        source_url = listing.detail_urls.get(source)
        await upsert_canonical_entity(
            session,
            workspace_id=workspace_id,
            entity_type=_BDS_ENTITY_TYPE,
            fingerprint=fingerprint,
            title=listing.title,
            data=canonical_data,
            search_text=search_text_value,
            source_name=source,
            source_record_id=source_record_id,
            source_snapshot=source_snapshot,
            source_url=source_url,
            confidence_score=listing.confidence_score,
            conflict_flags=conflict_flags,
        )


async def _stage_bds_persist_outbox(
    session: AsyncSession,
    workspace_id: int,
    listing: VnBdsAggregatedListing,
    error: str,
) -> None:
    """Stage a durable outbox row so a retry worker can finish persistence."""
    data = _build_bds_data(listing)
    canonical_data = _build_bds_canonical_data(listing, data)
    payload = {
        "workspace_id": workspace_id,
        "entity_type": _BDS_ENTITY_TYPE,
        "fingerprint": listing.canonical_id,
        "title": listing.title,
        "data": canonical_data,
        "search_text": search_text(listing),
        "sources": [
            {
                "source_name": source,
                "source_record_id": str(
                    listing.source_ids.get(source)
                    if listing.source_ids.get(source) is not None
                    else source
                ),
                "source_url": listing.detail_urls.get(source),
            }
            for source in listing.sources
        ],
    }
    await set_canonical_workspace_id(session, workspace_id)
    await create_persist_outbox(
        session,
        workspace_id=workspace_id,
        entity_type=_BDS_ENTITY_TYPE,
        payload=payload,
        error=error,
    )


async def _persist_bds_aggregates(
    session: AsyncSession | None,
    workspace_id: int | None,
    listings: list[VnBdsAggregatedListing],
) -> tuple[Literal["ok", "partial", "failed", "not_attempted"], str | None]:
    """Persist all listings and report ok/partial/failed/not_attempted."""
    if not session or workspace_id is None:
        return "not_attempted", None

    succeeded = False
    failed = False
    message: str | None = None

    for listing in listings:
        try:
            await _persist_bds_listing(session, workspace_id, listing)
            succeeded = True
        except Exception as exc:
            failed = True
            message = str(exc)
            logger.exception("BDS listing %s failed to persist", listing.canonical_id)
            record_canonical_persist_failure(
                domain="vn_bds",
                reason=categorize_exception(exc),
            )
            try:
                await _stage_bds_persist_outbox(
                    session, workspace_id, listing, str(exc)
                )
            except Exception:
                logger.exception(
                    "BDS persist outbox for %s also failed",
                    listing.canonical_id,
                )

    if failed and not succeeded:
        return "failed", message
    if failed:
        return "partial", "One or more listings failed to persist"
    return "ok", None


async def _execute_source(
    source: str,
    payload: VnBdsAggregateInput,
    source_executors: dict[str, Callable[..., Awaitable[Any]]] | None,
) -> tuple[list[dict[str, Any]], int, bool, str | None]:
    """Run one child scraper and return (items, cost, degraded, reason)."""
    child_dict, err = _build_child_payload(source, payload)
    if err:
        logger.warning("vn_bds.aggregate cannot build payload for %s: %s", source, err)
        return [], 0, True, err

    try:
        if source_executors and source in source_executors:
            child_output = await source_executors[source](child_dict)
        else:
            capability = get_capability(f"{source}.scrape")
            child_input = capability.input_schema(**child_dict)
            child_output = await capability.executor(child_input)
    except ValidationError as exc:
        logger.warning("vn_bds.aggregate validation error for %s: %s", source, exc)
        return [], 0, True, "invalid_input"
    except Exception as exc:
        logger.exception("vn_bds.aggregate source %s failed: %s", source, exc)
        return [], 0, True, "api_error"

    if child_output is None:
        return [], 0, True, "unknown"

    items, _, degraded, reason = _child_result(child_output)
    cost = _child_cost(items, source, child_output)
    if degraded:
        # Degraded child runs are not billed.
        cost = 0

    return items, cost, degraded, reason


async def aggregate(
    payload: VnBdsAggregateInput,
    source_executors: dict[str, Callable[..., Awaitable[Any]]] | None = None,
    *,
    workspace_id: int | None = None,
    session: AsyncSession | None = None,
) -> VnBdsAggregateOutput:
    """Fan out to selected sources, normalize, dedupe, score, and persist."""
    selected = payload.sources

    coros = [_execute_source(s, payload, source_executors) for s in selected]
    results = await asyncio.gather(*coros, return_exceptions=True)

    normalized: list[VnBdsAggregatedListing] = []
    source_breakdown: dict[str, Any] = {}
    degradation_reasons: list[str] = []
    any_degraded = False
    child_cost_total = 0

    provenance_input = payload.model_dump(exclude_unset=True)

    for source, result in zip(selected, results, strict=True):
        if isinstance(result, BaseException):
            logger.exception("vn_bds.aggregate unhandled exception from %s", source)
            source_breakdown.update(_source_breakdown(source, [], 0, True, "api_error"))
            degradation_reasons.append(f"{source}: api_error")
            any_degraded = True
            continue

        items, cost, degraded, reason = result
        child_cost_total += cost
        source_breakdown.update(
            _source_breakdown(source, items, cost, degraded, reason)
        )
        if degraded:
            any_degraded = True
            if reason:
                degradation_reasons.append(f"{source}: {reason}")
            continue

        for raw in items:
            try:
                listing = normalize_listing(source, raw)
                listing.provenance.source_input = provenance_input
                normalized.append(listing)
            except Exception:
                logger.exception("vn_bds.aggregate normalize failed for %s", source)

    deduped = deduplicate(normalized)
    scored = [score_listing(listing) for listing in deduped]
    filtered = _filter_by_confidence(scored, payload.min_confidence)
    filtered.sort(key=lambda listing: listing.confidence_score, reverse=True)

    total_items = len(filtered)
    aggregate_fee = (
        int(config.VN_BDS_AGGREGATE_QUERY_MICROS_PER_QUERY) if total_items > 0 else 0
    )
    cost_micros = child_cost_total + aggregate_fee

    persistence_status, persistence_message = await _persist_bds_aggregates(
        session, workspace_id, filtered
    )

    return VnBdsAggregateOutput(
        items=filtered,
        cost_micros=cost_micros,
        degraded=any_degraded,
        degradation_reasons=degradation_reasons,
        source_breakdown=source_breakdown,
        persistence_status=persistence_status,
        persistence_message=persistence_message,
    )

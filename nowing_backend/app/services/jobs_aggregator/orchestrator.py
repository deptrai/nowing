"""``jobs_aggregator`` orchestrator: fan-out, normalize, deduplicate, score."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from app.services.pii.redact import redact_job_pii

from .dedupe import deduplicate
from .normalize import normalize_listing
from .schemas import VnJobAggregatedListing, VnJobAggregateInput, VnJobAggregateOutput


def _redact_listing(listing: VnJobAggregatedListing) -> VnJobAggregatedListing:
    """Mask PII in job description and requirement text before returning."""
    for field in ("job_description", "job_requirement"):
        value = getattr(listing, field)
        if value:
            redacted = redact_job_pii(value)
            setattr(listing, field, redacted.text)
            if redacted.has_pii:
                listing.pii_redacted = True
    return listing


def _score_output(items: list[VnJobAggregatedListing]) -> tuple[float, float]:
    """Compute aggregate confidence and salary consistency scores."""
    if not items:
        return 0.0, 0.0
    avg_confidence = sum(item.confidence_score for item in items) / len(items)
    avg_salary_consistency = sum(item.salary_consistency_score for item in items) / len(items)
    return round(avg_confidence, 2), round(avg_salary_consistency, 2)


def _source_payload(input: VnJobAggregateInput, source: str) -> dict[str, Any]:
    """Build a source-specific scrape payload from the aggregate input."""
    payload: dict[str, Any] = {
        "keyword": input.keyword,
        "location": input.location,
        "salary_min": input.salary_min,
        "salary_max": input.salary_max,
        "employment_type": input.employment_type,
        "max_pages": input.max_pages,
        "max_items": input.max_items_per_source,
    }
    if source == "vietnamworks":
        # VietnamWorks public API uses locationId; keeping the string here
        # for parity with other sources. The aggregator filters by location
        # after normalization.
        payload.pop("location", None)
    return {k: v for k, v in payload.items() if v is not None}


async def _call_source(
    source: str,
    payload: dict[str, Any],
    ctx: Any,
) -> dict[str, Any]:
    """Invoke a single source capability and return a degraded-aware dict."""
    from app.capabilities.core import execute_with_context, get_capability
    from app.capabilities.core.types import Capability

    try:
        cap: Capability = get_capability(f"{source}.scrape")
    except KeyError:
        return {"items": [], "degraded": True, "degradation_reason": f"{source}: capability_not_found"}

    try:
        input_obj = cap.input_schema(**payload)
    except Exception as exc:
        return {"items": [], "degraded": True, "degradation_reason": f"{source}: invalid_input ({exc})"}

    try:
        result = await execute_with_context(cap.executor, payload=input_obj, ctx=ctx)
    except Exception as exc:
        return {"items": [], "degraded": True, "degradation_reason": f"{source}: {exc}"}

    if hasattr(result, "model_dump"):
        return result.model_dump()
    return dict(result)


async def aggregate_jobs(input: VnJobAggregateInput, ctx: Any) -> VnJobAggregateOutput:
    """Run the multi-source job aggregation pipeline."""
    output = VnJobAggregateOutput()
    output.source_breakdown = {source: {"total": 0, "degraded": False, "degradation_reason": None} for source in input.sources}

    all_listings: list[VnJobAggregatedListing] = []
    total_cost_micros = 0

    for source in input.sources:
        payload = _source_payload(input, source)
        raw = await _call_source(source, payload, ctx)

        source_items = raw.get("items", [])
        source_degraded = raw.get("degraded", False)
        source_reason = raw.get("degradation_reason") or raw.get("degradation_reasons", [None])[0]

        output.source_breakdown[source] = {
            "total": len(source_items),
            "degraded": source_degraded,
            "degradation_reason": source_reason,
        }

        if source_degraded:
            output.degraded = True
            if source_reason:
                output.degradation_reasons.append(f"{source}: {source_reason}")
            continue

        for item in source_items:
            listing = normalize_listing(source, item)
            listing = _redact_listing(listing)
            all_listings.append(listing)

        total_cost_micros += raw.get("cost_micros", 0) or raw.get("total_cost_micros", 0)

    output.items = deduplicate(all_listings)
    output.cost_micros = total_cost_micros
    output.confidence_score, output.salary_consistency_score = _score_output(output.items)

    # Apply aggregator-level location filter if provided.
    if input.location:
        loc = input.location.lower().strip()
        output.items = [item for item in output.items if (item.location or "").lower().strip() == loc]

    return output


def build_aggregate_executor() -> Awaitable[Any]:
    """Factory matching the capability executor pattern."""

    async def execute(input: VnJobAggregateInput, ctx: Any) -> VnJobAggregateOutput:
        return await aggregate_jobs(input, ctx)

    return execute

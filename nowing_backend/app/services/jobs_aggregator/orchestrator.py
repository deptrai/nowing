"""``jobs_aggregator`` orchestrator: fan-out, normalize, deduplicate, score, persist."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Awaitable
from datetime import UTC
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.metrics import record_vn_jobs_pii_detected
from app.services.location_normalize import resolve_city_code
from app.services.pii.redact import redact_job_pii
from app.services.scraper_chunks.serializer import to_chunks

from .dedupe import deduplicate
from .normalize import normalize_listing
from .schemas import VnJobAggregatedListing, VnJobAggregateInput, VnJobAggregateOutput

logger = logging.getLogger(__name__)

_JOBS_ENTITY_TYPE = "vn_job"

# Map raw degradation reasons to canonical enum (AC-3).
_DEGRADATION_ENUM_MAP: dict[str, str] = {
    "tos_pending": "SOURCE_FAILED",
    "capability_not_found": "SOURCE_FAILED",
    "invalid_input": "SOURCE_FAILED",
    "429": "RATE_LIMIT",
    "rate_limit": "RATE_LIMIT",
    "rate limited": "RATE_LIMIT",
    "403": "ANTI_BOT",
    "captcha": "ANTI_BOT",
    "anti_bot": "ANTI_BOT",
    "anti-bot": "ANTI_BOT",
    "partial": "PARTIAL_DATA",
}


def _map_degradation_reason(raw_reason: str | None) -> str:
    """Map a raw source degradation reason to a canonical enum value."""
    if not raw_reason:
        return "SOURCE_FAILED"
    lower = raw_reason.lower().strip()
    # Strip the "{source}: " prefix if present.
    if ":" in lower:
        lower = lower.split(":", 1)[1].strip()
    for key, enum_val in _DEGRADATION_ENUM_MAP.items():
        if key in lower:
            return enum_val
    return "SOURCE_FAILED"


def _redact_listing(listing: VnJobAggregatedListing) -> VnJobAggregatedListing:
    """Mask PII in job description and requirement text before returning."""
    total_counts = {"phone": 0, "email": 0, "name": 0}
    for field in ("job_description", "job_requirement"):
        value = getattr(listing, field)
        if value:
            redacted = redact_job_pii(value)
            setattr(listing, field, redacted.text)
            if redacted.has_pii:
                listing.pii_redacted = True
            # ponytail: per-field counts; total may exceed if the same PII
            # appears in both fields, but audit only needs counts, not values.
            # Upgrade path: deduplicate PII across fields if audit requires
            # exact totals (see story 12-4c-4d-4e-pii-ingest-exposure.md).
            total_counts["phone"] += redacted.phones_detected
            total_counts["email"] += redacted.emails_detected
            total_counts["name"] += redacted.names_detected

    if any(total_counts.values()):
        for pii_type, count in total_counts.items():
            record_vn_jobs_pii_detected(
                source=listing.source, pii_type=pii_type, count=count
            )
        logger.info(
            "PII redacted for listing",
            extra={
                "source": listing.source,
                "listing_id": listing.id,
                "phones": total_counts["phone"],
                "emails": total_counts["email"],
                "names": total_counts["name"],
            },
        )
    return listing


def _score_output(items: list[VnJobAggregatedListing]) -> tuple[float, float]:
    """Compute aggregate confidence and salary consistency scores."""
    if not items:
        return 0.0, 0.0
    avg_confidence = sum(item.confidence_score for item in items) / len(items)
    avg_salary_consistency = sum(item.salary_consistency_score for item in items) / len(
        items
    )
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
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": "capability_not_found",
        }

    try:
        input_obj = cap.input_schema(**payload)
    except Exception:
        logger.exception("Source %s input validation failed", source)
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": "invalid_input",
        }

    try:
        result = await execute_with_context(cap.executor, payload=input_obj, ctx=ctx)
    except Exception:
        logger.exception("Source %s scrape execution failed", source)
        return {"items": [], "degraded": True, "degradation_reason": "source_failed"}

    if hasattr(result, "model_dump"):
        return result.model_dump()
    return dict(result)


def _make_json_safe(value: Any) -> Any:
    """Recursively coerce Pydantic/date values for JSONB storage."""
    if isinstance(value, dict):
        return {k: _make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(v) for v in value]
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value.isoformat()
    return value


def _job_to_chunks(listing: VnJobAggregatedListing, fetched_at: str) -> Any:
    """Serialize one job aggregated listing into scraper ``Chunk[]``."""
    return to_chunks(
        domain="vn_jobs",
        data=listing,
        fetched_at=fetched_at,
        content_type="job",
        category="job_posting",
    )


async def _persist_jobs_aggregates(
    session: AsyncSession | None,
    workspace_id: int | None,
    listings: list[VnJobAggregatedListing],
) -> tuple[Literal["ok", "partial", "failed", "not_attempted"], str | None]:
    """Persist all listings to chainlens-research and report status."""
    if not session or not isinstance(session, AsyncSession) or workspace_id is None:
        return "not_attempted", None

    if not listings:
        return "ok", None

    chunks: list[Any] = []
    fetched_at = datetime.datetime.now(UTC).isoformat()
    for listing in listings:
        try:
            chunks.extend(_job_to_chunks(listing, fetched_at))
        except Exception:
            logger.exception("Job listing %s chunk serialization failed", listing.id)

    if not chunks:
        return "ok", None

    try:
        from app.services.chainlens.ingest import NowingIngestService

        ingest_service = NowingIngestService()
        await ingest_service.ingest(
            scraper_id="vn_jobs",
            chunks=chunks,
            workspace_id=workspace_id,
            session=None,
        )
        return "ok", None
    except Exception as exc:
        logger.exception("Job aggregate chainlens ingest failed")
        return "failed", str(exc)


async def aggregate_jobs(input: VnJobAggregateInput, ctx: Any) -> VnJobAggregateOutput:
    """Run the multi-source job aggregation pipeline."""
    output = VnJobAggregateOutput()
    output.source_breakdown = {
        source: {"total": 0, "degraded": False, "degradation_reason": None}
        for source in input.sources
    }

    all_listings: list[VnJobAggregatedListing] = []
    total_cost_micros = 0

    import asyncio

    async def _fetch_one(source: str) -> tuple[str, dict[str, Any]]:
        payload = _source_payload(input, source)
        try:
            raw = await _call_source(source, payload, ctx)
        except Exception:
            logger.exception("Source %s capability call failed", source)
            raw = {
                "items": [],
                "degraded": True,
                "degradation_reason": "source_failed",
            }
        if raw is None:
            raw = {"items": [], "degraded": False}
        return source, raw

    results = await asyncio.gather(*[_fetch_one(s) for s in input.sources])

    for source, raw in results:
        source_items = raw.get("items", [])
        source_degraded = raw.get("degraded", False)
        source_reason = (
            raw.get("degradation_reason") or raw.get("degradation_reasons", [None])[0]
        )

        output.source_breakdown[source] = {
            "total": len(source_items),
            "degraded": source_degraded,
            "degradation_reason": source_reason,
        }

        if source_degraded:
            output.degraded = True
            output.degraded_source_ids.append(source)
            canonical_reason = _map_degradation_reason(source_reason)
            output.degradation_reasons.append(canonical_reason)
            continue

        for item in source_items:
            listing = normalize_listing(source, item)
            listing = _redact_listing(listing)
            all_listings.append(listing)

        total_cost_micros += raw.get("cost_micros", 0) or raw.get(
            "total_cost_micros", 0
        )

    output.items = deduplicate(all_listings)
    output.cost_micros = total_cost_micros
    output.confidence_score, output.salary_consistency_score = _score_output(
        output.items
    )

    # Apply aggregator-level location filter if provided.
    # ponytail: resolve both sides to city codes so "Hà Nội" / "hanoi" / "HN" all match.
    # Upgrade path: use a canonical location taxonomy (e.g. Geonames) for
    # fuzzy matching and avoid ad-hoc normalisation.
    if input.location:
        loc_code = resolve_city_code(input.location) or input.location.lower().strip()
        output.items = [
            item
            for item in output.items
            if (
                resolve_city_code(item.location)
                or (item.location or "").lower().strip()
            )
            == loc_code
        ]

    session = getattr(ctx, "session", None)
    workspace_id = getattr(ctx, "workspace_id", None)
    (
        output.persistence_status,
        output.persistence_message,
    ) = await _persist_jobs_aggregates(session, workspace_id, output.items)

    return output


def build_aggregate_executor() -> Awaitable[Any]:
    """Factory matching the capability executor pattern."""

    async def execute(input: VnJobAggregateInput, ctx: Any) -> VnJobAggregateOutput:
        return await aggregate_jobs(input, ctx)

    return execute

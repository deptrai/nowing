"""``jobs_aggregator`` orchestrator: fan-out, normalize, deduplicate, score, persist."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Awaitable
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import (
    create_persist_outbox,
    upsert_canonical_entity,
)
from app.canonical.services.canonical_pii import redact_canonical_data
from app.canonical.tenant_context import set_canonical_workspace_id
from app.observability.metrics import (
    categorize_exception,
    record_canonical_persist_failure,
    record_vn_jobs_pii_detected,
)
from app.services.location_normalize import resolve_city_code
from app.services.pii.redact import redact_job_pii

from .dedupe import deduplicate, fingerprint, search_text
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


def _build_canonical_data(listing: VnJobAggregatedListing) -> dict[str, Any]:
    """Return a JSON-safe, PII-redacted copy of the listing for canonical storage."""
    # PrivateAttrs are excluded by Pydantic; description/requirement are already
    # redacted by _redact_listing before deduplication.
    return _make_json_safe(listing.model_dump())


def _build_job_source_snapshot(canonical_data: dict[str, Any]) -> dict[str, Any]:
    """Return a source snapshot with any remaining PII removed from text fields."""
    # ponytail: central redactor masks JD text and removes contact/email
    # heuristics; we keep the source snapshot consistent with canonical rules.
    # Upgrade path: replace with a domain-specific NER redactor if name/address
    # detection needs to improve (see story 12-4c-4d-4e-pii-ingest-exposure.md).
    return redact_canonical_data("vn_job", dict(canonical_data))


def _build_conflict_flags(
    listing: VnJobAggregatedListing,
) -> list[dict[str, Any]]:
    """Surface salary/location conflict metadata for canonical storage."""
    return [{"type": flag} for flag in listing.conflict_flags]


async def _stage_jobs_persist_outbox(
    session: AsyncSession,
    workspace_id: int,
    listing: VnJobAggregatedListing,
    error: str,
) -> None:
    """Stage a durable outbox row so a retry worker can finish persistence."""
    canonical_data = _build_canonical_data(listing)
    payload = {
        "workspace_id": workspace_id,
        "entity_type": _JOBS_ENTITY_TYPE,
        "fingerprint": fingerprint(listing.model_dump()),
        "title": listing.title,
        "data": canonical_data,
        "search_text": search_text(listing),
        "sources": [
            {
                "source_name": source_name,
                "source_record_id": source_record_id,
                "source_url": listing._source_url_map.get(source_name),
            }
            for source_name, source_record_id in listing._source_record_ids.items()
        ],
    }
    await set_canonical_workspace_id(session, workspace_id)
    await create_persist_outbox(
        session,
        workspace_id=workspace_id,
        entity_type=_JOBS_ENTITY_TYPE,
        payload=payload,
        error=error,
    )


async def _persist_jobs_aggregates(
    session: AsyncSession | None,
    workspace_id: int | None,
    listings: list[VnJobAggregatedListing],
) -> tuple[Literal["ok", "partial", "failed", "not_attempted"], str | None]:
    """Persist all listings and report ok/partial/failed/not_attempted."""
    if not session or not isinstance(session, AsyncSession) or workspace_id is None:
        return "not_attempted", None

    overall_succeeded = False
    overall_failed = False
    message: str | None = None

    for listing in listings:
        canonical_data = _build_canonical_data(listing)
        source_snapshot = _build_job_source_snapshot(canonical_data)
        fp = fingerprint(listing.model_dump())
        search_text_value = search_text(listing)
        conflict_flags = _build_conflict_flags(listing)

        listing_succeeded = False
        listing_failed = False
        listing_error: str | None = None

        # ponytail: each source record is linked against the same canonical
        # fingerprint; the unique (workspace, entity_type, source, record_id)
        # key keeps retries idempotent.
        # Upgrade path: batch upserts if per-source loop becomes a bottleneck
        for source_name, source_record_id in listing._source_record_ids.items():
            source_url = listing._source_url_map.get(source_name)
            try:
                await upsert_canonical_entity(
                    session,
                    workspace_id=workspace_id,
                    entity_type=_JOBS_ENTITY_TYPE,
                    fingerprint=fp,
                    title=listing.title,
                    data=canonical_data,
                    search_text=search_text_value,
                    source_name=source_name,
                    source_record_id=source_record_id,
                    source_snapshot=source_snapshot,
                    source_url=source_url,
                    confidence_score=listing.confidence_score,
                    conflict_flags=conflict_flags,
                )
                listing_succeeded = True
                overall_succeeded = True
            except Exception as exc:
                listing_failed = True
                overall_failed = True
                listing_error = str(exc)
                if message is None:
                    message = listing_error
                logger.exception(
                    "Job listing %s source %s failed to persist",
                    listing.id,
                    source_name,
                )
                record_canonical_persist_failure(
                    domain="vn_job",
                    reason=categorize_exception(exc),
                )

        if listing_failed:
            try:
                await _stage_jobs_persist_outbox(
                    session, workspace_id, listing, listing_error or "unknown"
                )
            except Exception:
                logger.exception(
                    "Job persist outbox for %s also failed",
                    listing.id,
                )

        if listing_succeeded:
            overall_succeeded = True

    if overall_failed and not overall_succeeded:
        return "failed", message
    if overall_failed:
        return "partial", message or "One or more job listings failed to persist"
    return "ok", None


async def aggregate_jobs(input: VnJobAggregateInput, ctx: Any) -> VnJobAggregateOutput:
    """Run the multi-source job aggregation pipeline."""
    output = VnJobAggregateOutput()
    output.source_breakdown = {
        source: {"total": 0, "degraded": False, "degradation_reason": None}
        for source in input.sources
    }

    all_listings: list[VnJobAggregatedListing] = []
    total_cost_micros = 0

    for source in input.sources:
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

        # Handle None return from _call_source (treat as empty, not degraded).
        if raw is None:
            raw = {"items": [], "degraded": False}

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

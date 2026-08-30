"""ChainLens research and job-market metric instruments."""

from __future__ import annotations

from functools import lru_cache

from app.observability.metrics.base import _add, _get_meter, _record

# Closed vocabulary for ``engine_reason``. Any value outside this set is
# redacted before it reaches a metric label so exception messages, upstream
# text, or run content cannot leak into telemetry.
_CHAINLENS_ENGINE_REASON_VOCABULARY: frozenset[str] = frozenset(
    {
        "not_configured",
        "timeout",
        "unreachable",
        "auth_failed",
        "rate_limited",
        "upstream_error",
        "stream_incomplete",
        "fallback_kb_hits",
        "fallback_kb_empty",
        "fallback_kb_error",
        "partial",
        "insufficient_evidence",
    }
)


@lru_cache(maxsize=1)
def _chainlens_degradation():
    return _get_meter().create_counter(
        "nowing.chainlens.degradation",
        description="Count of ChainLens research degradations by reason and outcome.",
    )


@lru_cache(maxsize=1)
def _chainlens_ingest_failed():
    return _get_meter().create_counter(
        "nowing.chainlens.ingest.failed",
        description="Count of failed chainlens-research scraper ingest batches.",
    )


@lru_cache(maxsize=1)
def _chainlens_auth_failed():
    return _get_meter().create_counter(
        "nowing.chainlens.auth_failed",
        description="Count of chainlens-research service-to-service auth failures.",
    )


@lru_cache(maxsize=1)
def _chainlens_private_search():
    return _get_meter().create_counter(
        "nowing.chainlens.private_search",
        description="Count of chainlens-research private data searches.",
    )


@lru_cache(maxsize=1)
def _chainlens_token_rotated():
    return _get_meter().create_counter(
        "nowing.chainlens.token_rotated",
        description="Count of chainlens-research service token rotations.",
    )


@lru_cache(maxsize=1)
def _kb_fallback_hit_count():
    return _get_meter().create_histogram(
        "nowing.chainlens.fallback_kb_hits",
        unit="{hit}",
        description="Number of workspace KB chunks used as ChainLens fallback citations.",
    )


@lru_cache(maxsize=1)
def _blocked_url_coverage():
    return _get_meter().create_counter(
        "nowing.chainlens.blocked_url_coverage",
        description="Count of blocked URLs by block type (URL redacted from labels).",
    )


@lru_cache(maxsize=1)
def _anti_bot_detection_total():
    return _get_meter().create_counter(
        "nowing.anti_bot.detection_total",
        description="Count of anti-bot/CAPTCHA detections by capability, block type, and domain.",
    )


@lru_cache(maxsize=1)
def _anti_bot_screenshot_failure():
    return _get_meter().create_counter(
        "nowing.anti_bot.screenshot_failure",
        description="Count of anti-bot screenshot capture or upload failures.",
    )


@lru_cache(maxsize=1)
def _chainlens_latency():
    return _get_meter().create_histogram(
        "nowing.chainlens.latency",
        unit="ms",
        description="ChainLens research latency by requested mode and metric type.",
    )


@lru_cache(maxsize=1)
def _vn_jobs_source_block():
    return _get_meter().create_counter(
        "nowing.vn_jobs.source_block",
        description="Count of source-level blocks/degradations in the job vertical.",
    )


@lru_cache(maxsize=1)
def _vn_jobs_pii_detected():
    return _get_meter().create_counter(
        "nowing.vn_jobs.pii_detected",
        description="Count of PII entities detected in job descriptions.",
    )


@lru_cache(maxsize=1)
def _vn_jobs_aggregate_degraded():
    return _get_meter().create_counter(
        "nowing.vn_jobs.aggregate_degraded",
        description="Count of degraded vn_jobs.aggregate invocations.",
    )


def _fallback_hit_bucket(count: int) -> str:
    if count == 0:
        return "0"
    if count <= 5:
        return "1-5"
    return "6+"


def _redact_engine_reason(engine_reason: str | None) -> str | None:
    """Return a low-cardinality engine reason or ``None`` if missing."""
    if not engine_reason:
        return None
    normalized = engine_reason.strip().lower()
    return (
        normalized if normalized in _CHAINLENS_ENGINE_REASON_VOCABULARY else "redacted"
    )


def record_chainlens_private_search(
    *,
    workspace_id: int,
    result: str,
    hit_count: int,
) -> None:
    """Count one chainlens-research private data search."""
    _add(
        _chainlens_private_search(),
        1,
        {
            "workspace_id": str(workspace_id),
            "result": result,
            "hit_bucket": _fallback_hit_bucket(hit_count),
        },
    )


def record_chainlens_auth_failed(
    *,
    workspace_id: int,
    reason: str,
) -> None:
    """Count one chainlens-research service-to-service auth failure."""
    _add(
        _chainlens_auth_failed(),
        1,
        {
            "workspace_id": str(workspace_id),
            "reason": reason,
        },
    )


def record_chainlens_token_rotated(
    *,
    workspace_id: int,
    reason: str,
) -> None:
    """Count one chainlens-research service token rotation."""
    _add(
        _chainlens_token_rotated(),
        1,
        {
            "workspace_id": str(workspace_id),
            "reason": reason,
        },
    )


def record_anti_bot_detection(*, capability: str, block_type: str, domain: str) -> None:
    _add(
        _anti_bot_detection_total(),
        1,
        {"capability": capability, "block_type": block_type, "domain": domain},
    )


def record_anti_bot_screenshot_failure(*, reason: str) -> None:
    _add(_anti_bot_screenshot_failure(), 1, {"reason": reason})


def record_chainlens_degradation(
    *,
    degradation_reason: str,
    final_status: str,
    fallback_attempted: bool,
    fallback_used: bool,
    fallback_hit_count: int,
    engine_reason: str | None = None,
) -> None:
    """Count one ChainLens research degradation."""
    _add(
        _chainlens_degradation(),
        1,
        {
            "degradation_reason": degradation_reason,
            "final_status": final_status,
            "fallback_attempted": bool(fallback_attempted),
            "fallback_used": bool(fallback_used),
            "engine_reason": _redact_engine_reason(engine_reason) or "none",
        },
    )


def record_kb_fallback_hit_count(fallback_hit_count: int) -> None:
    """Record how many workspace KB chunks were cited in a degraded fallback."""
    if fallback_hit_count < 0:
        return
    _record(
        _kb_fallback_hit_count(),
        fallback_hit_count,
        {"hit_bucket": _fallback_hit_bucket(fallback_hit_count)},
    )


def record_blocked_url_coverage(*, block_type: str) -> None:
    """Count one blocked URL by its block type; the URL never enters labels."""
    _add(_blocked_url_coverage(), 1, {"block_type": block_type})


def record_chainlens_latency(
    *, duration_ms: int, metric: str, mode: str | None = None
) -> None:
    """Record one e2e or TTFB latency observation for ChainLens research."""
    if duration_ms is None or duration_ms < 0:
        return
    labels: dict[str, str] = {"metric": metric}
    if mode:
        labels["mode"] = mode
    _record(_chainlens_latency(), duration_ms, labels)


def record_chainlens_ingest_failed(
    *,
    scraper_id: str,
    workspace_id: int,
    status_code: int,
    error: str,
) -> None:
    """Count one failed or exhausted chainlens-research scraper ingest batch."""
    _add(
        _chainlens_ingest_failed(),
        1,
        {
            "scraper_id": scraper_id,
            "workspace_id": str(workspace_id),
            "status_code": str(status_code),
            "error": error,
        },
    )


def record_vn_jobs_source_block(*, source: str, reason: str) -> None:
    """Count one source-level block in the job vertical."""
    _add(_vn_jobs_source_block(), 1, {"source": source, "reason": reason})


def record_vn_jobs_pii_detected(*, source: str, pii_type: str, count: int) -> None:
    """Count PII entities detected in a job listing. Values are not emitted."""
    if count <= 0:
        return
    _add(_vn_jobs_pii_detected(), count, {"source": source, "pii_type": pii_type})


def record_vn_jobs_aggregate_degraded(*, reason: str) -> None:
    """Count one degraded vn_jobs.aggregate invocation."""
    _add(_vn_jobs_aggregate_degraded(), 1, {"reason": reason})

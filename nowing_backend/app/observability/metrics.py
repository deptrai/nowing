"""Custom OpenTelemetry metrics for Nowing.

This module owns all Nowing-specific metric instruments. Callers use the
small helper functions below instead of constructing instruments directly so
attribute names and cardinality stay consistent across the backend.
"""

from __future__ import annotations

import contextlib
import gc
import logging
from functools import lru_cache
from importlib import metadata
from typing import Any

from app.observability import otel

logger = logging.getLogger(__name__)

_INSTRUMENTATION_NAME = "nowing.platform"
_OBSERVABLES_REGISTERED = False
_ERROR_CATEGORY_UNKNOWN = "unknown"

_ERROR_CATEGORY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rate_limited", ("ratelimit", "rate_limit", "toomanyrequests", "429")),
    ("auth_failed", ("authentication", "auth", "unauthorized", "forbidden")),
    ("quota_exhausted", ("quota", "insufficient", "credit", "billing")),
    ("timeout", ("timeout", "timedout", "deadline")),
    ("network_failed", ("connection", "connect", "network", "dns", "socket")),
    ("server_error", ("internalserver", "serviceunavailable", "badgateway", "gateway")),
    ("lock_contention", ("lock", "busy", "contention", "alreadyrunning")),
    ("unsupported_format", ("unsupported", "format", "filetype")),
    ("provider_error", ("provider", "apierror", "apistatus", "badrequest")),
)


def _package_version() -> str:
    # Best-effort telemetry tag only: never let a version lookup crash the
    # request path. Besides PackageNotFoundError, a malformed/dynamic editable
    # install can have distribution metadata with no "Version" field, which
    # raises KeyError deep in importlib.metadata. Suppress broadly.
    with contextlib.suppress(Exception):
        return metadata.version("surf-new-backend")
    return "unknown"


def _is_enabled() -> bool:
    return otel.is_enabled()


def _clean_attrs(attrs: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Drop empty values and coerce low-cardinality attrs to OTel-safe scalars."""
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, bool | int | float):
            cleaned[key] = value
            continue
        text = str(value)
        if text:
            cleaned[key] = text
    return cleaned


def _attrs_with_optional_error_category(
    attrs: dict[str, Any], error_category: str | None
) -> dict[str, Any]:
    if error_category:
        return {**attrs, "error.category": error_category}
    return attrs


def categorize_exception(exc: BaseException | None) -> str:
    """Return a low-cardinality category for an exception."""
    if exc is None:
        return _ERROR_CATEGORY_UNKNOWN
    haystack = " ".join(
        cls.__name__.replace("-", "").replace("_", "").lower()
        for cls in type(exc).__mro__
    )
    for category, hints in _ERROR_CATEGORY_HINTS:
        if any(hint in haystack for hint in hints):
            return category
    return _ERROR_CATEGORY_UNKNOWN


def parse_celery_task_label(task_name: str | None) -> str:
    """Return the operation token from a Celery task name."""
    if not task_name:
        return "unknown"
    operation = str(task_name).split("_", 1)[0].strip()
    return operation or "unknown"


def _record(callable_obj: Any, value: int | float, attrs: dict[str, Any]) -> None:
    if not _is_enabled():
        return
    with contextlib.suppress(Exception):
        callable_obj.record(value, _clean_attrs(attrs))


def _add(callable_obj: Any, value: int, attrs: dict[str, Any]) -> None:
    if not _is_enabled():
        return
    with contextlib.suppress(Exception):
        callable_obj.add(value, _clean_attrs(attrs))


@lru_cache(maxsize=1)
def _get_meter():
    from opentelemetry import metrics

    return metrics.get_meter(_INSTRUMENTATION_NAME, _package_version())


@lru_cache(maxsize=1)
def _model_call_duration():
    return _get_meter().create_histogram(
        "nowing.model.call.duration",
        unit="ms",
        description="Duration of Nowing LLM model calls.",
    )


@lru_cache(maxsize=1)
def _model_token_usage():
    return _get_meter().create_histogram(
        "gen_ai.client.token.usage",
        unit="{token}",
        description="Token usage reported by GenAI model responses.",
    )


@lru_cache(maxsize=1)
def _tool_call_duration():
    return _get_meter().create_histogram(
        "nowing.tool.call.duration",
        unit="ms",
        description="Duration of Nowing agent tool calls.",
    )


@lru_cache(maxsize=1)
def _tool_call_errors():
    return _get_meter().create_counter(
        "nowing.tool.call.errors",
        description="Count of Nowing agent tool call errors.",
    )


@lru_cache(maxsize=1)
def _kb_search_duration():
    return _get_meter().create_histogram(
        "nowing.kb.search.duration",
        unit="ms",
        description="Duration of Nowing knowledge-base search calls.",
    )


@lru_cache(maxsize=1)
def _compaction_runs():
    return _get_meter().create_counter(
        "nowing.compaction.runs",
        description="Count of Nowing conversation compaction runs.",
    )


@lru_cache(maxsize=1)
def _permission_asks():
    return _get_meter().create_counter(
        "nowing.permission.asks",
        description="Count of Nowing permission asks.",
    )


@lru_cache(maxsize=1)
def _interrupts():
    return _get_meter().create_counter(
        "nowing.interrupt.raised",
        description="Count of Nowing interrupts raised.",
    )


@lru_cache(maxsize=1)
def _indexing_document_duration():
    return _get_meter().create_histogram(
        "nowing.indexing.document.duration",
        unit="s",
        description="Duration of Nowing document indexing.",
    )


@lru_cache(maxsize=1)
def _indexing_document_outcome():
    return _get_meter().create_counter(
        "nowing.indexing.document.outcome",
        description="Count of Nowing document indexing outcomes.",
    )


@lru_cache(maxsize=1)
def _connector_sync_duration():
    return _get_meter().create_histogram(
        "nowing.connector.sync.duration",
        unit="s",
        description="Duration of Nowing connector sync tasks.",
    )


@lru_cache(maxsize=1)
def _connector_sync_outcome():
    return _get_meter().create_counter(
        "nowing.connector.sync.outcome",
        description="Count of Nowing connector sync outcomes.",
    )


@lru_cache(maxsize=1)
def _auth_failures():
    return _get_meter().create_counter(
        "nowing.auth.failures",
        description="Count of Nowing authentication failures.",
    )


@lru_cache(maxsize=1)
def _rate_limit_rejections():
    return _get_meter().create_counter(
        "nowing.rate_limit.rejections",
        description="Count of Nowing rate-limit rejections.",
    )


@lru_cache(maxsize=1)
def _perf_elapsed():
    return _get_meter().create_histogram(
        "nowing.perf.elapsed_ms",
        unit="ms",
        description="Elapsed time recorded by Nowing perf timers.",
    )


@lru_cache(maxsize=1)
def _chat_request_duration():
    return _get_meter().create_histogram(
        "nowing.chat.request.duration",
        unit="ms",
        description="Duration of Nowing streamed chat requests.",
    )


@lru_cache(maxsize=1)
def _chat_request_outcome():
    return _get_meter().create_counter(
        "nowing.chat.request.outcome",
        description="Count of Nowing chat request outcomes.",
    )


@lru_cache(maxsize=1)
def _agent_chat_public_call():
    return _get_meter().create_counter(
        "nowing.agent_chat.public_call",
        description="Count of public agent-chat API calls.",
    )


@lru_cache(maxsize=1)
def _subagent_invoke_duration():
    return _get_meter().create_histogram(
        "nowing.subagent.invoke.duration",
        unit="ms",
        description="Duration of Nowing subagent invocations.",
    )


@lru_cache(maxsize=1)
def _subagent_invoke_outcome():
    return _get_meter().create_counter(
        "nowing.subagent.invoke.outcome",
        description="Count of Nowing subagent invocation outcomes.",
    )


@lru_cache(maxsize=1)
def _etl_extract_duration():
    return _get_meter().create_histogram(
        "nowing.etl.extract.duration",
        unit="s",
        description="Duration of Nowing ETL extraction.",
    )


@lru_cache(maxsize=1)
def _etl_extract_outcome():
    return _get_meter().create_counter(
        "nowing.etl.extract.outcome",
        description="Count of Nowing ETL extraction outcomes.",
    )


@lru_cache(maxsize=1)
def _etl_cache_lookups():
    return _get_meter().create_counter(
        "nowing.etl.cache.lookups",
        description="Count of ETL parse-cache lookups by outcome (hit/miss).",
    )


@lru_cache(maxsize=1)
def _etl_cache_evictions():
    return _get_meter().create_counter(
        "nowing.etl.cache.evictions",
        description="Count of ETL parse-cache entries evicted, by phase.",
    )


@lru_cache(maxsize=1)
def _embedding_cache_lookups():
    return _get_meter().create_counter(
        "nowing.embedding.cache.lookups",
        description="Count of embedding (chunk+embedding) cache lookups by outcome (hit/miss).",
    )


@lru_cache(maxsize=1)
def _embedding_cache_evictions():
    return _get_meter().create_counter(
        "nowing.embedding.cache.evictions",
        description="Count of embedding cache entries evicted, by phase.",
    )


@lru_cache(maxsize=1)
def _chunk_reconcile_chunks():
    return _get_meter().create_counter(
        "nowing.indexing.reconcile.chunks",
        description=(
            "Chunks handled by incremental re-indexing, by outcome "
            "(reused/embedded/deleted)."
        ),
    )


@lru_cache(maxsize=1)
def _celery_heartbeat_refreshes():
    return _get_meter().create_counter(
        "nowing.celery.heartbeat.refreshes",
        description="Count of Nowing Celery heartbeat refreshes.",
    )


@lru_cache(maxsize=1)
def _celery_heartbeat_failures():
    return _get_meter().create_counter(
        "nowing.celery.heartbeat.failures",
        description="Count of Nowing Celery heartbeat failures.",
    )


@lru_cache(maxsize=1)
def _celery_queue_latency():
    return _get_meter().create_histogram(
        "nowing.celery.queue.latency",
        unit="s",
        description="Time Nowing Celery tasks spend waiting in queue.",
    )


@lru_cache(maxsize=1)
def _gateway_redis_fallback():
    return _get_meter().create_counter(
        "nowing.gateway.redis.fallback",
        description="Count of gateway Redis fallback uses.",
    )


@lru_cache(maxsize=1)
def _gateway_thread_lock_contention():
    return _get_meter().create_counter(
        "nowing.gateway.thread_lock.contention",
        description="Count of gateway per-thread lock contention events.",
    )


@lru_cache(maxsize=1)
def _gateway_inbox_writes():
    return _get_meter().create_counter(
        "nowing.gateway.inbox.writes",
        description="Count of gateway inbound event inbox writes.",
    )


@lru_cache(maxsize=1)
def _gateway_inbox_processed():
    return _get_meter().create_counter(
        "nowing.gateway.inbox.processed",
        description="Count of gateway inbound event processing outcomes.",
    )


@lru_cache(maxsize=1)
def _gateway_inbound_reconciled():
    return _get_meter().create_counter(
        "nowing.gateway.inbound.reconciled",
        description="Count of gateway inbox events re-enqueued by reconciliation.",
    )


@lru_cache(maxsize=1)
def _gateway_outbound():
    return _get_meter().create_counter(
        "nowing.gateway.outbound",
        description="Count of gateway outbound platform operations.",
    )


@lru_cache(maxsize=1)
def _gateway_turn_latency():
    return _get_meter().create_histogram(
        "nowing.gateway.turn.latency",
        unit="ms",
        description="Latency of gateway-routed agent turns.",
    )


@lru_cache(maxsize=1)
def _gateway_rate_limit_hits():
    return _get_meter().create_counter(
        "nowing.gateway.rate_limit.hits",
        description="Count of gateway outbound rate limit waits.",
    )


@lru_cache(maxsize=1)
def _gateway_health_check_failures():
    return _get_meter().create_counter(
        "nowing.gateway.health_check.failures",
        description="Count of gateway account health-check failures.",
    )


@lru_cache(maxsize=1)
def _gateway_auth_invariant_failures():
    return _get_meter().create_counter(
        "nowing.gateway.auth_invariant.failures",
        description="Count of gateway authorization invariant failures.",
    )


@lru_cache(maxsize=1)
def _gateway_hitl_aborted():
    return _get_meter().create_counter(
        "nowing.gateway.hitl.aborted",
        description="Count of gateway turns aborted because HITL is unsupported.",
    )


@lru_cache(maxsize=1)
def _gateway_active_bindings():
    return _get_meter().create_up_down_counter(
        "nowing.gateway.active_bindings",
        description="Current change in active gateway bindings.",
    )


@lru_cache(maxsize=1)
def _gateway_inbox_enqueued():
    return _get_meter().create_counter(
        "gateway_inbox_enqueued_total",
        description="Count of gateway inbox rows enqueued for worker processing.",
    )


@lru_cache(maxsize=1)
def _gateway_inbox_sweep_replayed():
    return _get_meter().create_counter(
        "gateway_inbox_sweep_replayed_total",
        description="Count of received gateway inbox rows replayed by the sweep.",
    )


@lru_cache(maxsize=1)
def _gateway_byo_longpoll_running():
    return _get_meter().create_up_down_counter(
        "gateway_byo_longpoll_running",
        description="Current change in BYO Telegram long-poll supervisors holding a poll loop.",
    )


@lru_cache(maxsize=1)
def _gateway_webhook_parse_errors():
    return _get_meter().create_counter(
        "gateway_webhook_parse_error_total",
        description="Count of malformed gateway webhook payloads.",
    )


# ── Run-derived memory extraction (Story 3.13, T6/AC-9) ──────────────────────
# Deliberately low-cardinality: the only attribute any of these carries is the
# already-enumerated skip `reason` vocabulary from Story 8.7/8.8. No capability
# name (15 values today but operator-extensible), no workspace/run id, and never
# any scraped payload — AC-9 requires metric labels to stay free of run content.


@lru_cache(maxsize=1)
def _run_memory_enqueued():
    return _get_meter().create_counter(
        "run_memory_enqueued_total",
        description="Count of successful capability runs enqueued for memory extraction.",
    )


@lru_cache(maxsize=1)
def _run_memory_created():
    return _get_meter().create_counter(
        "run_memory_created_total",
        description="Count of durable memories created from capability runs.",
    )


@lru_cache(maxsize=1)
def _run_memory_zero_fact():
    return _get_meter().create_counter(
        "run_memory_zero_fact_total",
        description="Count of run extractions that succeeded but yielded no qualifying fact.",
    )


@lru_cache(maxsize=1)
def _run_memory_skipped():
    return _get_meter().create_counter(
        "run_memory_skipped_total",
        description="Count of run extractions skipped by a gate or policy decision.",
    )


@lru_cache(maxsize=1)
def _run_memory_failed():
    return _get_meter().create_counter(
        "run_memory_failed_total",
        description="Count of run extractions that exhausted their retry budget or failed terminally.",
    )


@lru_cache(maxsize=1)
def _run_memory_retried():
    return _get_meter().create_counter(
        "run_memory_retried_total",
        description="Count of run extraction attempts re-scheduled after a transient failure.",
    )


def record_model_call_duration(
    duration_ms: float, *, model: str | None, provider: str | None
) -> None:
    _record(
        _model_call_duration(),
        duration_ms,
        {
            "gen_ai.request.model": model,
            "gen_ai.provider.name": provider,
        },
    )


def record_model_token_usage(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    model: str | None,
    provider: str | None,
) -> None:
    base = {
        "gen_ai.request.model": model,
        "gen_ai.provider.name": provider,
        "gen_ai.operation.name": "chat",
    }
    if input_tokens is not None:
        _record(
            _model_token_usage(),
            int(input_tokens),
            {**base, "gen_ai.token.type": "input"},
        )
    if output_tokens is not None:
        _record(
            _model_token_usage(),
            int(output_tokens),
            {**base, "gen_ai.token.type": "output"},
        )


def record_tool_call_duration(duration_ms: float, *, tool_name: str) -> None:
    _record(_tool_call_duration(), duration_ms, {"tool.name": tool_name})


def record_tool_call_error(*, tool_name: str) -> None:
    _add(_tool_call_errors(), 1, {"tool.name": tool_name})


def record_kb_search_duration(
    duration_ms: float, *, workspace_id: int | None, surface: str
) -> None:
    _record(
        _kb_search_duration(),
        duration_ms,
        {"workspace.id": workspace_id, "search.surface": surface},
    )


def record_compaction_run(*, reason: str | None) -> None:
    _add(_compaction_runs(), 1, {"compaction.reason": reason or "unknown"})


def record_permission_ask(*, permission: str) -> None:
    _add(_permission_asks(), 1, {"permission.permission": permission})


def record_interrupt(*, interrupt_type: str) -> None:
    _add(_interrupts(), 1, {"interrupt.type": interrupt_type})


def record_indexing_document_duration(
    duration_s: float, *, document_type: str | None
) -> None:
    _record(
        _indexing_document_duration(),
        duration_s,
        {"document.type": document_type or "unknown"},
    )


def record_indexing_document_outcome(*, document_type: str | None, status: str) -> None:
    _add(
        _indexing_document_outcome(),
        1,
        {"document.type": document_type or "unknown", "status": status},
    )


def record_connector_sync_duration(
    duration_s: float, *, connector_type: str | None
) -> None:
    _record(
        _connector_sync_duration(),
        duration_s,
        {"connector.type": connector_type or "unknown"},
    )


def record_connector_sync_outcome(
    *, connector_type: str | None, status: str, error_category: str | None = None
) -> None:
    _add(
        _connector_sync_outcome(),
        1,
        _attrs_with_optional_error_category(
            {"connector.type": connector_type or "unknown", "status": status},
            error_category,
        ),
    )


def record_auth_failure(*, reason: str) -> None:
    _add(_auth_failures(), 1, {"reason": reason})


def record_rate_limit_rejection(*, scope: str) -> None:
    _add(_rate_limit_rejections(), 1, {"scope": scope})


def record_perf_elapsed(duration_ms: float, *, label: str) -> None:
    _record(_perf_elapsed(), duration_ms, {"label": label})


def record_chat_request_duration(
    duration_ms: float,
    *,
    flow: str,
    outcome: str,
    agent_mode: str | None = None,
) -> None:
    _record(
        _chat_request_duration(),
        duration_ms,
        {"chat.flow": flow, "outcome": outcome, "agent.mode": agent_mode},
    )


def record_agent_chat_public_call(
    *,
    workspace_id: int | str,
    client_id: str | None,
    agent_id: str | None,
    route: str,
    status: int,
) -> None:
    _add(
        _agent_chat_public_call(),
        1,
        _clean_attrs(
            {
                "workspace.id": workspace_id,
                "client.id": client_id,
                "agent.id": agent_id,
                "route": route,
                "status": status,
            }
        ),
    )


def record_chat_request_outcome(
    *,
    flow: str,
    outcome: str,
    agent_mode: str | None = None,
    error_category: str | None = None,
) -> None:
    _add(
        _chat_request_outcome(),
        1,
        _attrs_with_optional_error_category(
            {"chat.flow": flow, "outcome": outcome, "agent.mode": agent_mode},
            error_category,
        ),
    )


def record_subagent_invoke_duration(
    duration_ms: float,
    *,
    subagent_type: str,
    path: str | None,
    outcome: str,
) -> None:
    _record(
        _subagent_invoke_duration(),
        duration_ms,
        {
            "subagent.type": subagent_type,
            "subagent.path": path or "unknown",
            "outcome": outcome,
        },
    )


def record_subagent_invoke_outcome(
    *,
    subagent_type: str,
    path: str | None,
    outcome: str,
) -> None:
    _add(
        _subagent_invoke_outcome(),
        1,
        {
            "subagent.type": subagent_type,
            "subagent.path": path or "unknown",
            "outcome": outcome,
        },
    )


def record_etl_extract_duration(
    duration_s: float,
    *,
    etl_service: str | None,
    content_type: str | None,
    status: str,
) -> None:
    _record(
        _etl_extract_duration(),
        duration_s,
        {
            "etl.service": etl_service or "unknown",
            "content.type": content_type or "unknown",
            "status": status,
        },
    )


def record_etl_extract_outcome(
    *,
    etl_service: str | None,
    content_type: str | None,
    status: str,
    error_category: str | None = None,
) -> None:
    _add(
        _etl_extract_outcome(),
        1,
        _attrs_with_optional_error_category(
            {
                "etl.service": etl_service or "unknown",
                "content.type": content_type or "unknown",
                "status": status,
            },
            error_category,
        ),
    )


def record_etl_cache_lookup(
    *, etl_service: str | None, mode: str | None, outcome: str
) -> None:
    """Record a parse-cache lookup. ``outcome`` is ``hit`` or ``miss``."""
    _add(
        _etl_cache_lookups(),
        1,
        {
            "etl.service": etl_service or "unknown",
            "mode": mode or "unknown",
            "outcome": outcome,
        },
    )


def record_etl_cache_eviction(count: int, *, phase: str) -> None:
    """Record evicted entries. ``phase`` is ``ttl`` or ``size``."""
    if count <= 0:
        return
    _add(_etl_cache_evictions(), count, {"phase": phase})


def record_embedding_cache_lookup(
    *, embedding_model: str | None, chunker_kind: str | None, outcome: str
) -> None:
    """Record an embedding-cache lookup. ``outcome`` is ``hit`` or ``miss``."""
    _add(
        _embedding_cache_lookups(),
        1,
        {
            "embedding.model": embedding_model or "unknown",
            "chunker.kind": chunker_kind or "unknown",
            "outcome": outcome,
        },
    )


def record_embedding_cache_eviction(count: int, *, phase: str) -> None:
    """Record evicted entries. ``phase`` is ``ttl`` or ``size``."""
    if count <= 0:
        return
    _add(_embedding_cache_evictions(), count, {"phase": phase})


def record_chunk_reconcile(*, reused: int, embedded: int, deleted: int) -> None:
    """Record an incremental re-index: how many chunks were kept vs recomputed."""
    for outcome, count in (
        ("reused", reused),
        ("embedded", embedded),
        ("deleted", deleted),
    ):
        if count > 0:
            _add(_chunk_reconcile_chunks(), count, {"outcome": outcome})


def record_celery_heartbeat_refresh(*, heartbeat_type: str) -> None:
    _add(_celery_heartbeat_refreshes(), 1, {"heartbeat.type": heartbeat_type})


def record_celery_heartbeat_failure(*, heartbeat_type: str) -> None:
    _add(_celery_heartbeat_failures(), 1, {"heartbeat.type": heartbeat_type})


def record_celery_queue_latency(
    duration_s: float,
    *,
    task_name: str | None,
    queue: str | None,
    scheduled: bool,
    operation: str | None,
) -> None:
    _record(
        _celery_queue_latency(),
        duration_s,
        {
            "task.name": task_name or "unknown",
            "task.queue": queue or "unknown",
            "task.scheduled": bool(scheduled),
            "operation": operation or "unknown",
        },
    )


def record_gateway_redis_fallback() -> None:
    _add(_gateway_redis_fallback(), 1, {})


def record_gateway_thread_lock_contention() -> None:
    _add(_gateway_thread_lock_contention(), 1, {})


def record_gateway_inbox_write(*, platform: str, dedup_skipped: bool) -> None:
    _add(
        _gateway_inbox_writes(),
        1,
        {"platform": platform, "dedup.skipped": bool(dedup_skipped)},
    )


def record_gateway_inbox_processed(*, platform: str, status: str) -> None:
    _add(_gateway_inbox_processed(), 1, {"platform": platform, "status": status})


def record_gateway_inbound_reconciled(*, reason: str) -> None:
    _add(_gateway_inbound_reconciled(), 1, {"reason": reason})


def record_gateway_outbound(*, platform: str, kind: str, status: str) -> None:
    _add(
        _gateway_outbound(),
        1,
        {"platform": platform, "kind": kind, "status": status},
    )


def record_gateway_turn_latency(duration_ms: float, *, platform: str) -> None:
    _record(_gateway_turn_latency(), duration_ms, {"platform": platform})


def record_gateway_rate_limit_hit(*, bucket: str) -> None:
    _add(_gateway_rate_limit_hits(), 1, {"bucket": bucket})


def record_gateway_health_check_failure(*, platform: str) -> None:
    _add(_gateway_health_check_failures(), 1, {"platform": platform})


def record_gateway_auth_invariant_failure(*, cause: str) -> None:
    _add(_gateway_auth_invariant_failures(), 1, {"cause": cause})


def record_gateway_hitl_aborted(*, platform: str) -> None:
    _add(_gateway_hitl_aborted(), 1, {"platform": platform})


def record_gateway_active_bindings_delta(delta: int, *, platform: str) -> None:
    _add(_gateway_active_bindings(), delta, {"platform": platform})


def record_gateway_inbox_enqueued(*, intake: str, outcome: str) -> None:
    _add(_gateway_inbox_enqueued(), 1, {"intake": intake, "outcome": outcome})


def record_gateway_inbox_sweep_replayed() -> None:
    _add(_gateway_inbox_sweep_replayed(), 1, {})


def record_gateway_byo_longpoll_running_delta(delta: int, *, account_id: int) -> None:
    _add(_gateway_byo_longpoll_running(), delta, {"account_id": account_id})


def record_gateway_webhook_parse_error() -> None:
    _add(_gateway_webhook_parse_errors(), 1, {})


def record_run_memory_enqueued() -> None:
    """One successful run handed to the extraction queue (AC-9).

    Counted at the enqueue seam, not at task start: the funnel's first stage is
    "the run became eligible", and a broker outage that drops the message must
    show up as enqueued-without-created rather than vanishing entirely.
    """
    _add(_run_memory_enqueued(), 1, {})


def record_run_memory_created(count: int = 1) -> None:
    """``count`` durable memories were committed from one run extraction."""
    if count <= 0:
        return
    _add(_run_memory_created(), count, {})


def record_run_memory_zero_fact() -> None:
    """A run extraction ran the LLM successfully and found nothing worth keeping.

    Distinct from ``skipped``: the spend already happened, so collapsing the two
    would hide the case where extraction is running and costing money while
    producing no recall value.
    """
    _add(_run_memory_zero_fact(), 1, {})


def record_run_memory_skipped(*, reason: str) -> None:
    """A run extraction was skipped before the LLM call.

    ``reason`` must come from the Story 8.7/8.8 vocabulary (``disabled``,
    ``anonymous_unbilled``, ``insufficient_wallet``, ``budget_exceeded``,
    ``rate_limited``, ``gate_error``, ``missing_creator``, ``empty_output``,
    ``context_window``, ``no_llm``) — a closed set, which is what keeps this
    label low-cardinality.
    """
    _add(_run_memory_skipped(), 1, {"reason": reason})


def record_run_memory_failed() -> None:
    _add(_run_memory_failed(), 1, {})


def record_run_memory_retried() -> None:
    _add(_run_memory_retried(), 1, {})


_memory_injection_failure_logger = logging.getLogger("memory_injection.failure")


@lru_cache(maxsize=1)
def _memory_injection_failures():
    return _get_meter().create_counter(
        "nowing.memory.injection.failures",
        description="Count of memory injection failures by scope/stage/reason.",
    )


def record_memory_injection_failure(*, scope: str, stage: str, reason: str) -> None:
    """Log + count exactly one ordinary memory injection failure attempt.

    D8: the single owner of both the ``memory_injection.failure`` log and the
    ``nowing.memory.injection.failures`` counter — callers must invoke this at
    most once per failed attempt (precedence is resolved by the caller).
    """
    attrs = {"scope": scope, "stage": stage, "reason": reason}
    with contextlib.suppress(Exception):
        _memory_injection_failure_logger.warning(
            "memory_injection.failure", extra=attrs
        )
    with contextlib.suppress(Exception):
        _add(_memory_injection_failures(), 1, attrs)


def _runtime_snapshot_value(key: str, transform: Any = None) -> list[Any]:
    from opentelemetry.metrics import Observation

    from app.utils.perf import system_snapshot

    snap = system_snapshot()
    value = snap.get(key)
    if not isinstance(value, int | float) or value < 0:
        return []
    if transform is not None:
        value = transform(value)
    return [Observation(value)]


def _observe_gc_collections(_options: Any) -> list[Any]:
    from opentelemetry.metrics import Observation

    return [
        Observation(count, {"generation": str(generation)})
        for generation, count in enumerate(gc.get_count())
    ]


def register_runtime_observables() -> None:
    """Register process/runtime observable gauges once per process."""
    global _OBSERVABLES_REGISTERED
    if _OBSERVABLES_REGISTERED or not _is_enabled():
        return

    meter = _get_meter()
    try:
        # Each callback returns the value for a single gauge except GC, whose
        # callback carries a generation attribute.
        meter.create_observable_gauge(
            "process.runtime.cpython.memory.rss",
            callbacks=[
                lambda _options: _runtime_snapshot_value(
                    "rss_mb", lambda v: float(v) * 1024 * 1024
                )
            ],
            unit="By",
            description="Resident set size of the Nowing backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.cpu.utilization",
            callbacks=[
                lambda _options: _runtime_snapshot_value(
                    "cpu_percent", lambda v: float(v) / 100.0
                )
            ],
            unit="1",
            description="CPU utilization of the Nowing backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.threads",
            callbacks=[lambda _options: _runtime_snapshot_value("threads")],
            unit="{thread}",
            description="Thread count of the Nowing backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.open_fds",
            callbacks=[lambda _options: _runtime_snapshot_value("open_fds")],
            unit="{fd}",
            description="Open file descriptor count of the Nowing backend process.",
        )
        meter.create_observable_gauge(
            "python.asyncio.tasks",
            callbacks=[lambda _options: _runtime_snapshot_value("asyncio_tasks")],
            unit="{task}",
            description="Live asyncio task count in the current event loop.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.gc.collections",
            callbacks=[_observe_gc_collections],
            unit="{collection}",
            description="CPython GC counters by generation.",
        )
    except Exception:
        logger.warning("Failed to register OTel runtime observables", exc_info=True)
        return

    _OBSERVABLES_REGISTERED = True


# ── ChainLens research degradation (Story 9.1a) ──────────────────────────────
# Low-cardinality telemetry: degradation_reason and final_status are from a
# closed vocabulary; the user's query, API key, and answer are intentionally
# NOT included in metric labels.


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


def record_anti_bot_detection(*, capability: str, block_type: str, domain: str) -> None:
    _add(
        _anti_bot_detection_total(),
        1,
        {"capability": capability, "block_type": block_type, "domain": domain},
    )


def record_anti_bot_screenshot_failure(*, reason: str) -> None:
    _add(_anti_bot_screenshot_failure(), 1, {"reason": reason})


def _redact_engine_reason(engine_reason: str | None) -> str | None:
    """Return a low-cardinality engine reason or ``None`` if missing.

    Values matching the closed vocabulary are normalized to lowercase. Anything
    else is redacted to ``"redacted"`` to keep arbitrary exception messages,
    query text, and upstream responses out of metric labels.
    """
    if not engine_reason:
        return None
    normalized = engine_reason.strip().lower()
    return (
        normalized if normalized in _CHAINLENS_ENGINE_REASON_VOCABULARY else "redacted"
    )


def record_chainlens_degradation(
    *,
    degradation_reason: str,
    final_status: str,
    fallback_attempted: bool,
    fallback_used: bool,
    fallback_hit_count: int,
    engine_reason: str | None = None,
) -> None:
    """Count one ChainLens research degradation.

    Only low-cardinality reason/status labels are emitted. Query text, URLs,
    answer text, API keys, workspace ids, and user ids are never accepted or
    recorded. ``engine_reason`` is enforced against a closed vocabulary; any
    arbitrary value is redacted to ``"redacted"`` before it is emitted.
    """
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


def _fallback_hit_bucket(count: int) -> str:
    if count == 0:
        return "0"
    if count <= 5:
        return "1-5"
    return "6+"


def record_kb_fallback_hit_count(fallback_hit_count: int) -> None:
    """Record how many workspace KB chunks were cited in a degraded fallback.

    The exact value is recorded on the histogram; the label is a small bucket
    to keep cardinality low.
    """
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


@lru_cache(maxsize=1)
def _chainlens_latency():
    return _get_meter().create_histogram(
        "nowing.chainlens.latency",
        unit="ms",
        description="ChainLens research latency by requested mode and metric type.",
    )


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


@lru_cache(maxsize=1)
def _run_event_bus_dropped():
    return _get_meter().create_counter(
        "nowing.run_event_bus.events.dropped",
        description="Count of run-event bus events dropped before delivery.",
    )


def record_run_event_bus_dropped(*, reason: str = "queue_full") -> None:
    _add(_run_event_bus_dropped(), 1, {"reason": reason})


# ── Job-market / PII redaction telemetry (Epic 12) ──────────────────────────
# Low-cardinality: source, block_type, and pii_type only. Values are never
# emitted; only counts.


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


def record_vn_jobs_source_block(*, source: str, reason: str) -> None:
    """Count one source-level block in the job vertical.

    ``reason`` must be a low-cardinality closed value; arbitrary messages are
    the caller's responsibility to normalize.
    """
    _add(_vn_jobs_source_block(), 1, {"source": source, "reason": reason})


def record_vn_jobs_pii_detected(*, source: str, pii_type: str, count: int) -> None:
    """Count PII entities detected in a job listing. Values are not emitted."""
    if count <= 0:
        return
    _add(_vn_jobs_pii_detected(), count, {"source": source, "pii_type": pii_type})


def record_vn_jobs_aggregate_degraded(*, reason: str) -> None:
    """Count one degraded vn_jobs.aggregate invocation."""
    _add(_vn_jobs_aggregate_degraded(), 1, {"reason": reason})


@lru_cache(maxsize=1)
def _canonical_persist_failed():
    return _get_meter().create_counter(
        "nowing.canonical.persist.failed",
        description="Count of canonical persistence failures.",
    )


def record_canonical_persist_failure(*, domain: str, reason: str) -> None:
    """Count one terminal canonical persistence failure by domain."""
    _add(_canonical_persist_failed(), 1, {"domain": domain, "reason": reason})


__all__ = [
    "categorize_exception",
    "parse_celery_task_label",
    "record_anti_bot_detection",
    "record_anti_bot_screenshot_failure",
    "record_auth_failure",
    "record_blocked_url_coverage",
    "record_canonical_persist_failure",
    "record_celery_heartbeat_failure",
    "record_celery_heartbeat_refresh",
    "record_celery_queue_latency",
    "record_chainlens_degradation",
    "record_chainlens_ingest_failed",
    "record_chainlens_latency",
    "record_chat_request_duration",
    "record_chat_request_outcome",
    "record_chunk_reconcile",
    "record_compaction_run",
    "record_connector_sync_duration",
    "record_connector_sync_outcome",
    "record_embedding_cache_eviction",
    "record_embedding_cache_lookup",
    "record_etl_cache_eviction",
    "record_etl_cache_lookup",
    "record_etl_extract_duration",
    "record_etl_extract_outcome",
    "record_indexing_document_duration",
    "record_indexing_document_outcome",
    "record_interrupt",
    "record_kb_fallback_hit_count",
    "record_kb_search_duration",
    "record_memory_injection_failure",
    "record_model_call_duration",
    "record_model_token_usage",
    "record_perf_elapsed",
    "record_permission_ask",
    "record_rate_limit_rejection",
    "record_run_event_bus_dropped",
    "record_subagent_invoke_duration",
    "record_subagent_invoke_outcome",
    "record_tool_call_duration",
    "record_tool_call_error",
    "record_vn_jobs_aggregate_degraded",
    "record_vn_jobs_pii_detected",
    "record_vn_jobs_source_block",
    "register_runtime_observables",
]

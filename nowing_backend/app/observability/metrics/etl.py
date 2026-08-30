"""ETL, indexing, embedding-cache, and Celery metric instruments."""

from __future__ import annotations

from functools import lru_cache

from app.observability.metrics.base import (
    _add,
    _attrs_with_optional_error_category,
    _get_meter,
    _record,
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

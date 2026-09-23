"""External chat gateway metric instruments."""

from __future__ import annotations

from functools import lru_cache

from app.observability.metrics.base import _add, _get_meter, _record


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

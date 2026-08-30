"""Platform-wide metric instruments: auth, rate limits, perf."""

from __future__ import annotations

from functools import lru_cache

from app.observability.metrics.base import _add, _get_meter, _record


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
def _run_event_bus_dropped():
    return _get_meter().create_counter(
        "nowing.run_event_bus.events.dropped",
        description="Count of run-event bus events dropped before delivery.",
    )


def record_auth_failure(*, reason: str) -> None:
    _add(_auth_failures(), 1, {"reason": reason})


def record_rate_limit_rejection(*, scope: str) -> None:
    _add(_rate_limit_rejections(), 1, {"scope": scope})


def record_perf_elapsed(duration_ms: float, *, label: str) -> None:
    _record(_perf_elapsed(), duration_ms, {"label": label})


def record_run_event_bus_dropped(*, reason: str = "queue_full") -> None:
    _add(_run_event_bus_dropped(), 1, {"reason": reason})

"""Runtime and process-level metric observables."""

from __future__ import annotations

import logging

from app.observability.metrics import base as _base

logger = logging.getLogger(__name__)

_OBSERVABLES_REGISTERED = False


def register_runtime_observables() -> None:
    """Register process/runtime observable gauges once per process."""
    global _OBSERVABLES_REGISTERED
    if _OBSERVABLES_REGISTERED or not _base._is_enabled():
        return

    meter = _base._get_meter()
    try:
        meter.create_observable_gauge(
            "process.runtime.cpython.memory.rss",
            callbacks=[
                lambda _options: _base._base._runtime_snapshot_value(
                    "rss_mb", lambda v: float(v) * 1024 * 1024
                )
            ],
            unit="By",
            description="Resident set size of the Nowing backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.cpu.utilization",
            callbacks=[
                lambda _options: _base._runtime_snapshot_value(
                    "cpu_percent", lambda v: float(v) / 100.0
                )
            ],
            unit="1",
            description="CPU utilization of the Nowing backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.threads",
            callbacks=[lambda _options: _base._runtime_snapshot_value("threads")],
            unit="{thread}",
            description="Thread count of the Nowing backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.open_fds",
            callbacks=[lambda _options: _base._runtime_snapshot_value("open_fds")],
            unit="{fd}",
            description="Open file descriptor count of the Nowing backend process.",
        )
        meter.create_observable_gauge(
            "python.asyncio.tasks",
            callbacks=[lambda _options: _base._runtime_snapshot_value("asyncio_tasks")],
            unit="{task}",
            description="Live asyncio task count in the current event loop.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.gc.collections",
            callbacks=[_base._observe_gc_collections],
            unit="{collection}",
            description="CPython GC counters by generation.",
        )
    except Exception:
        logger.warning("Failed to register OTel runtime observables", exc_info=True)
        return

    _OBSERVABLES_REGISTERED = True
